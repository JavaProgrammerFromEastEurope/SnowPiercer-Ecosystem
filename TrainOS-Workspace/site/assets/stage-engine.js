(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.SnowPiercerStages = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const stages = Object.freeze([
    ['inventory', 'I', 'Инвентаризация'], ['architecture', 'II', 'Архитектура'],
    ['development', 'III', 'Разработка'], ['modelling', 'IV', 'Моделирование'],
    ['verification', 'V', 'Испытания'], ['integration', 'VI', 'Интеграция'],
    ['operations', 'VII', 'Эксплуатация'], ['evolution', 'VIII', 'Развитие']
  ].map(([id, roman, name]) => Object.freeze({id, roman, name})));
  const requiredModules = Object.freeze(['SP-RAIL','SP-LIFE','SP-AI','SP-LOG','SP-ENERGY','SP-ISLAND']);
  const registryIds = Object.freeze(['SP-SW',...requiredModules,'SP-SAFE','SP-OPS']);
  const sha = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
  const namedArtifact = a => a?.status === 'accepted' && sha(a.sha256) && typeof a.path === 'string' && a.path.trim().length > 0;
  const item = (id, label, met, detail) => ({id,label,met:met === true,detail});
  const text = v => typeof v === 'string' && v.length > 0;
  function records(snapshot) { return Array.isArray(snapshot?.modules) ? snapshot.modules : []; }
  function completeRegistry(snapshot) {
    const values = snapshot?.registry;
    return Array.isArray(values) && values.length === 9 &&
      new Set(values.map(m=>m.moduleId)).size === 9 &&
      registryIds.every(id=>values.some(m=>m.moduleId === id && text(m.status) &&
        Array.isArray(m.dependencies) && m.dependencies.every(d=>registryIds.includes(d))));
  }
  function completeInventory(snapshot) {
    const values = records(snapshot);
    return values.length === 6 && new Set(values.map(m=>m.moduleId)).size === 6 &&
      requiredModules.every(id=>values.some(m=>m.moduleId === id && text(m.sourceStage) && text(m.targetStage) &&
        sha(m.sourceArchive?.sha256) && text(m.sourceArchive?.name) &&
        text(m.sourceIntegrity?.status) && Array.isArray(m.limits) &&
        Array.isArray(m.requirements) && m.requirements.length > 0 &&
        m.requirements.every(r=>text(r.id) && text(r.criterion) && text(r.evidence))));
  }
  function softwareVerified(snapshot) {
    return completeInventory(snapshot) && records(snapshot).every(m=>m.status === 'SOFTWARE_VERIFIED' &&
      m.tests?.failed === 0 && Number.isInteger(m.tests.passed) && m.tests.passed > 0 &&
      Number.isInteger(m.tests.skipped) && m.tests.skipped >= 0 && sha(m.artifact?.sha256));
  }
  function probeVerified(snapshot) {
    const p = snapshot?.integration;
    return p?.status === 'passed' && sha(p.reportSha256) && text(p.correlationId) &&
      Array.isArray(p.modules) && p.modules.length === 6 && new Set(p.modules.map(m=>m.moduleId)).size === 6 &&
      requiredModules.every(id=>p.modules.some(m=>m.moduleId === id && m.status === 'ok' &&
        m.schema === 'snowpiercer.integration-probe.v1' && m.stageId === records(snapshot).find(r=>r.moduleId === id)?.targetStage &&
        m.correlationId === p.correlationId && m.operationalReady === false &&
        Array.isArray(m.checks) && m.checks.length >= 2 && m.checks.every(c=>c.passed === true && text(c.name))));
  }
  function gates(index, snapshot) {
    const accepted = snapshot?.acceptance || {};
    switch (index) {
      case 0: return [
        item('registry','Все 9 подсистем перечислены с явными зависимостями и неизвестными состояниями',completeRegistry(snapshot),'Security и Operations могут иметь неизвестную готовность; это явно отражается в реестре.'),
        item('sources','Все 6 загруженных архивов учтены, требования и результаты проверки источников сохранены',completeInventory(snapshot),'Инвентаризация охватывает доступные материалы этой итерации, а не все будущие компоненты SnowPiercer.'),
        item('software','Для 6 направлений сохранены новые артефакты и результаты полной доступной регрессии',softwareVerified(snapshot),'Пропущенные проверки перечислены отдельно и не считаются пройденными.'),
        item('boundaries','Шесть реальных программных проверок соответствуют общему контракту наблюдения',probeVerified(snapshot),'Это локальная проверка границ API; она не подтверждает сопряжение оборудования.')
      ];
      case 1: return [
        item('interfaces','Версионированные интерфейсы согласованы с владельцами подсистем',namedArtifact(accepted.interfaces),'Нужен принятый документ со схемами сообщений, единицами, сроками, отказами и версиями.'),
        item('requirements','Утверждена привязка системных требований к интерфейсам',namedArtifact(accepted.requirements),'Текущие требования отдельных программных stages не заменяют системную приёмку.'),
        item('security','Независимо рассмотрены полномочия и отказобезопасное поведение',namedArtifact(accepted.securityReview),'Ссылки на заявленные документы должны попасть в новую проверенную версию снимка.')
      ];
      case 2: return [
        item('software','Доступные программные регрессии и общие проверки прошли',softwareVerified(snapshot) && probeVerified(snapshot),'Допуски физической эксплуатации этим не выдаются.'),
        item('implementation','Принят базовый набор программных и аппаратных компонентов',namedArtifact(accepted.implementation),'Требуется подтверждение владельцев реализации, включая незавершённые аппаратные части.')
      ];
      case 3: return [item('models','Приняты модели, сценарии и анализ отказов',namedArtifact(accepted.models),'Нужны измеряемые сценарии, исходные допущения и отчёты моделирования.')];
      case 4: return [item('systemTests','Приняты системные и физические испытания',namedArtifact(accepted.systemTests),'Программные probes текущей итерации не являются системными испытаниями.')];
      case 5: return [item('physicalIntegration','Приняты результаты сопряжения TrainOS с физическими подсистемами',namedArtifact(accepted.physicalIntegration),'Нужны действующие интеграционные протоколы и результаты испытаний оборудования.')];
      case 6: return [
        item('safety','Получена независимая приёмка безопасности',namedArtifact(accepted.safety),'Нужны подтверждённые требования и независимая проверка.'),
        item('operations','Приняты процедуры эксплуатации, мониторинга и обслуживания',namedArtifact(accepted.operations),'Требуются владельцы, процедуры, обучение и эксплуатационные доказательства.')
      ];
      case 7: return [];
      default: throw new Error('Неизвестный этап рабочего плана.');
    }
  }
  function initial(snapshot) {
    if (!text(snapshot?.iterationId) || !text(snapshot?.evidenceRevision)) throw new Error('Нет версии доказательств.');
    return {schema:'snowpiercer.workflow-state.v1',iterationId:snapshot.iterationId,
      evidenceRevision:snapshot.evidenceRevision,currentIndex:0,revision:0,history:[]};
  }
  function validate(state, snapshot) {
    if (state?.schema !== 'snowpiercer.workflow-state.v1' || state.iterationId !== snapshot?.iterationId ||
      !Number.isInteger(state.currentIndex) || state.currentIndex < 0 || state.currentIndex >= stages.length ||
      !Number.isInteger(state.revision) || state.revision !== state.currentIndex ||
      !Array.isArray(state.history) || state.history.length !== state.currentIndex || !text(state.evidenceRevision)) return false;
    return state.history.every((event,index)=>event && typeof event === 'object' && event.from === stages[index].id && event.to === stages[index+1].id &&
      event.revision === index+1 && event.iterationId === snapshot.iterationId && text(event.evidenceRevision) &&
      text(event.at) && Number.isFinite(Date.parse(event.at)) &&
      gates(index,snapshot).length > 0 && gates(index,snapshot).every(g=>g.met));
  }
  function assess(state, snapshot) {
    if (!validate(state,snapshot)) throw new Error('Состояние плана повреждено или относится к другой итерации.');
    const checks=gates(state.currentIndex,snapshot);
    return {current:stages[state.currentIndex],next:stages[state.currentIndex+1] || null,
      checks,allowed:state.currentIndex < stages.length-1 && checks.length > 0 && checks.every(g=>g.met)};
  }
  function advance(state, snapshot, request) {
    const result=assess(state,snapshot);
    if (request?.expectedRevision !== state.revision || request?.expectedStage !== result.current.id ||
      request?.evidenceRevision !== snapshot.evidenceRevision) throw new Error('План или доказательства изменились. Откройте переход заново.');
    if (!result.allowed) throw new Error(result.next ? 'Критерии следующего этапа ещё не выполнены.' : 'Это последний этап текущего плана.');
    if (!text(request.at) || !Number.isFinite(Date.parse(request.at))) throw new Error('Некорректное время перехода.');
    const nextRevision=state.revision+1;
    return {schema:state.schema,iterationId:state.iterationId,evidenceRevision:snapshot.evidenceRevision,
      currentIndex:state.currentIndex+1,revision:nextRevision,history:[...state.history,
        {from:result.current.id,to:result.next.id,revision:nextRevision,iterationId:state.iterationId,
          evidenceRevision:snapshot.evidenceRevision,at:new Date(request.at).toISOString()}]};
  }
  return Object.freeze({stages,requiredModules,initial,validate,assess,advance});
});
