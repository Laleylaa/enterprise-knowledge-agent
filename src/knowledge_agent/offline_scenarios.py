"""Explicit, bounded offline scripts using actual indexed tool observations.

These scripts demonstrate plumbing, never model reasoning or general question answering.
Faults are installed only on per-turn mock tool instances; real mode is untouched.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from knowledge_agent.reading.tool import ReadTool
from knowledge_agent.mock_model import scripted_answer

Scenario = Literal['normal', 'conflict', 'missing', 'tool_failure', 'recovery', 'budget']
QUESTIONS = {
    'normal': '国内差旅报销期限多久？',
    'conflict': '差旅报销期限多久？',
    'missing': '请查阅 D99 的规定。',
    'tool_failure': '国内差旅报销期限多久？',
    'recovery': '国内差旅报销期限多久？',
    'budget': '国内差旅报销期限多久？',
}


def validate_scenario_input(scenario: str, question: str):
    if question != QUESTIONS[scenario]:
        raise ValueError(f'MOCK_SCENARIO_UNSUPPORTED：{scenario} 仅支持固定输入“{QUESTIONS[scenario]}”，不提供通用离线问答。')


def create_scenario_model(scenario: Scenario) -> FunctionModel:
    def respond(messages, info):
        written = scripted_answer(messages, info, scenario)
        if written is not None:
            return written
        observations = [p.content for m in messages if isinstance(m, ModelRequest) for p in m.parts
                        if isinstance(p, ToolReturnPart) and isinstance(p.content, dict)
                        and p.content.get('schema_version') == 1]
        def call(name, args):
            return ModelResponse(parts=[ToolCallPart(name, args, tool_call_id=f'offline-{len(observations)+1}')])
        def finish(status, text, citations=(), gaps=(), clarification=None):
            return call('finish_research', dict(
                reason={'resolved':'sufficient','needs_info':'conflict',
                        'unresolved':'missing','incomplete':'blocked'}[status],
                decision_summary=f'离线预设 {scenario} 脚本停止取证；不证明模型决策能力。'))
        if scenario == 'budget':
            return call('search_knowledge', {'query':'国内差旅 报销 期限','purpose':'离线预算脚本：持续请求合法工具'})
        if not observations:
            if scenario in {'missing', 'tool_failure'}:
                return call('read_document', {'doc_id':'D99' if scenario == 'missing' else 'D01',
                                              'purpose':'离线脚本：实际读取指定原文'})
            return call('search_knowledge', {'query':'差旅 报销 期限','purpose':'离线脚本：实际检索期限条款'})
        latest = observations[-1]
        if latest['status'] == 'error':
            codes = {e['code'] for e in latest.get('errors', [])}
            if scenario == 'recovery' and len(observations) == 1 and codes & {'SEARCH_FAILED','READ_FAILED'}:
                return call('read_document', {'doc_id':'D01','purpose':'离线预设恢复分支：观察故障后改为读取'})
            if scenario == 'missing' and codes == {'NOT_FOUND'}:
                return finish('unresolved','本轮未取得 D99 原文，无法回答其规定；不据此断言制度不存在。',gaps=['缺少 D99 原文。'])
            return finish('incomplete','本轮工具执行失败，未能取得必要依据。',gaps=['原文取得失败，当前查证未完成。'])
        if scenario == 'conflict' and len(observations) == 1:
            return call('read_document', {'doc_id':'D01','purpose':'离线预设冲突分支：读取原文核实范围'})
        if scenario == 'conflict' and len(observations) == 2:
            return call('read_document', {'doc_id':'D02','purpose':'离线预设冲突分支：核实另一来源'})
        # Quotes are selected only from actual returned spans, never fabricated observations.
        items = [item for obs in observations for key in ('hits','segments') for item in obs.get('data',{}).get(key,[])]
        quotes = []
        for doc in (('D01','D02') if scenario == 'conflict' else ('D01',)):
            for item in reversed(items):
                if item['doc_id'] != doc: continue
                line = next((line.removeprefix('1. ').strip() for line in item['text'].splitlines()
                             if '差旅报销须在行程结束后' in line), None)
                if line:
                    quotes.append({'evidence_id':item['evidence_id'],'doc_id':doc,'quote':line})
                    break
        if (scenario == 'conflict' and len(quotes)==2
                and quotes[0]['quote']=='差旅报销须在行程结束后 30 天内提交。'
                and quotes[1]['quote']=='差旅报销须在行程结束后 15 天内提交。'):
            return finish('needs_info','两份原文分别规定30天与15天，当前脚本不选择适用制度。',quotes,
                          ['缺少可核实的适用关系。'],'请提供适用制度或可核实的范围线索。')
        if scenario in {'normal','recovery'} and len(quotes)==1 and '国内差旅' in quotes[0]['quote']:
            return finish('resolved',quotes[0]['quote'],quotes)
        return finish('incomplete','MOCK_SCENARIO_UNSUPPORTED：实际观察不满足该脚本前提。',
                      gaps=['需使用文档中声明的资料与场景；脚本不能推断其他制度。'])
    return FunctionModel(respond, model_name=f'offline-indexed-{scenario}-v1')


@dataclass
class OfflineFault:
    mode: str
    recorder: object
    attempts: int = 0

    def before(self, tool):
        self.attempts += 1
        inject = self.mode == 'always' or self.attempts == 1
        record = {'origin':'offline_mock_injection','mode':self.mode,'backend_attempts':self.attempts,
                  'last_tool':tool,'injected':inject,'not_live_service_failure':True}
        self.recorder.write('fault-injection.json',record)
        if inject:
            self.recorder.event('offline_fault_injected',origin='mock',**{k:v for k,v in record.items() if k!='origin'})
            raise OSError('explicit offline demonstration fault')


class FaultIndex:
    def __init__(self, index, fault):
        self.index, self.fault = index, fault

    def __getattr__(self, name):
        return getattr(self.index, name)

    def rank(self, *args, **kwargs):
        self.fault.before('search_knowledge')
        return self.index.rank(*args, **kwargs)

    def rank_result(self, query, doc_ids):
        from knowledge_agent.retrieval.backend import rank_sync
        self.fault.before('search_knowledge')
        return rank_sync(self.index, query, doc_ids)

    async def arank_result(self, query, doc_ids, *, deadline=None):
        from knowledge_agent.retrieval.backend import rank_async
        self.fault.before('search_knowledge')
        return await rank_async(self.index, query, doc_ids, deadline=deadline)

    def lookup(self, *args, **kwargs):
        self.fault.before('search_knowledge')
        return self.index.lookup(*args, **kwargs)


class FaultReader(ReadTool):
    def _select(self, request):
        self.offline_fault.before(self.name)
        return super()._select(request)
