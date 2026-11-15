(() => {
  'use strict';
  const D = window.TRAINOS_DATA;
  const V = window.TRAINOS_VERIFICATION || {status:'pending'};
  const E = window.SNOWPIERCER_DEVELOPMENT;
  const G = window.SnowPiercerStages;
  const developed = new Map((E?.modules || []).map(m=>[m.moduleId,m]));
  const page = document.getElementById('page');
  const icons = {
    overview:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    ecosystem:'M12 3v5 M5 16v-4h14v4 M12 8v8 M3 16h4v5H3z M10 16h4v5h-4z M17 16h4v5h-4z M10 3h4',
    layers:'m12 3 9 5-9 5-9-5 9-5z M3 12l9 5 9-5 M3 16l9 5 9-5',
    shield:'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3z m-4 9 3 3 5-6',
    contracts:'M8 8h8 M8 16h8 M3 5h5v6H3z M16 13h5v6h-5z M5 11v5h3 M19 13V8h-3',
    route:'M6 7a2 2 0 1 0 0-4 2 2 0 0 0 0 4z M18 21a2 2 0 1 0 0-4 2 2 0 0 0 0 4z M6 7v6a4 4 0 0 0 4 4h4 M18 17v-6a4 4 0 0 0-4-4h-4',
    checklist:'M9 5h11 M9 12h11 M9 19h11 m-16-14 1 1 2-2 m-3 8 1 1 2-2 m-3 8 1 1 2-2',
    download:'M12 3v12 m-5-5 5 5 5-5 M4 16v5h16v-5',
    info:'M12 17v-5 M12 8h.01 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
    menu:'M4 6h16 M4 12h16 M4 18h16',
    close:'m6 6 12 12 M6 18 18 6',
    plus:'M12 5v14 M5 12h14',
    arrow:'M5 12h14 m-5-5 5 5-5 5',
    search:'M16 16l5 5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
    code:'m8 6-6 6 6 6 M16 6l6 6-6 6 m-3-15-2 18',
    train:'M6 16V5c0-2 12-2 12 0v11l-3 3H9l-3-3z M6 11h12 M12 4v7 M9 15h.01 M15 15h.01 M8 21l2-2 M16 21l-2-2',
    ai:'M12 3v3 M12 18v3 M3 12h3 M18 12h3 M6 6l2 2 M16 16l2 2 M6 18l2-2 M16 8l2-2 M8 8h8v8H8z M11 11h2v2h-2z',
    energy:'m13 2-9 12h7l-1 8 10-13h-8l1-7z',
    life:'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8z M5 12h4l2-4 2 8 2-4h4',
    logistics:'M3 7l9-4 9 4-9 4-9-4z M3 7v10l9 4 9-4V7 M12 11v10 M7 5l10 4',
    island:'M3 21h18 M5 21V10l6 3V7l8 5v9 M8 17h.01 M13 17h.01 M17 17h.01 M15 5V2',
    ops:'M14 3h-4l-.6 3-2 .9-2.7-1.1-2 3.5L5 11v2l-2.3 1.7 2 3.5L7.4 17l2 .9.6 3.1h4l.6-3.1 2-.9 2.7 1.2 2-3.5L19 13v-2l2.3-1.7-2-3.5-2.7 1.1-2-.9L14 3z M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
    file:'M14 2H5v20h14V7l-5-5z M14 2v5h5 M8 12h8 M8 16h6',
    clock:'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0 M12 6v6l4 2',
    check:'m5 12 4 4L19 6',
    trash:'M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7',
    globe:'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0 M2 12h20 M12 2c-5 5-5 15 0 20 M12 2c5 5 5 15 0 20'
  };
  const icon = n => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${icons[n] || icons.layers}"/></svg>`;
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const badge = (text, kind='neutral', dot=false) => `<span class="badge ${kind}">${dot?'<span class="tiny-dot"></span>':''}${esc(text)}</span>`;
  const modules = {
    'SP-SW':{name:'TrainOS',subtitle:'Программное ядро и управление',icon:'code',status:'Активная разработка',kind:'good',next:'Завершить аудит требований, подтвердить CI, внешний платёжный sandbox и восстановление вне исходного узла.'},
    'SP-AI':{name:'AI / Cognition',subtitle:'Интеллектуальные системы',icon:'ai',status:'Инвентаризация',next:'Утвердить требования, протокол оценки, границы автономности и проверку вмешательства оператора.'},
    'SP-RAIL':{name:'Rail Systems',subtitle:'Поезда и инфраструктура',icon:'train',status:'Нужны доказательства',next:'Подготовить инженерную концепцию, анализ опасностей, модели тяги, торможения и сцепки.'},
    'SP-ENERGY':{name:'Energy',subtitle:'Генерация и распределение',icon:'energy',status:'Технико-экономическая оценка',next:'Сформировать профиль нагрузки, энергобаланс, архитектуру защиты и аварийных режимов.'},
    'SP-LIFE':{name:'Life Support',subtitle:'Жизнеобеспечение',icon:'life',status:'Инвентаризация',next:'Определить балансы воздуха, воды и ресурсов, медицинские требования и долгосрочную валидацию.'},
    'SP-LOG':{name:'Logistics',subtitle:'Грузы, роботы и дроны',icon:'logistics',status:'Инвентаризация',next:'Описать сквозные маршруты грузов, сверку запасов, геозоны и ручное управление.'},
    'SP-SAFE':{name:'Security',subtitle:'Защита и устойчивость',icon:'shield',status:'Нужна базовая модель',next:'Подготовить модель угроз, реестр опасностей, управление доступом и план независимой проверки.'},
    'SP-ISLAND':{name:'SnowPiercer Island',subtitle:'Физическая инфраструктура',icon:'island',status:'Декомпозиция объёма',next:'Определить требования к площадке, инженерную концепцию, разрешения и стоимость.'},
    'SP-OPS':{name:'Integration & Operations',subtitle:'Испытания и эксплуатация',icon:'ops',status:'Инвентаризация',next:'Зафиксировать роли, эксплуатационные процедуры, обслуживание, обучение и управление изменениями.'}
  };
  for (const [id, result] of developed) {
    if (modules[id]) {
      modules[id].status = result.targetStage;
      modules[id].kind = result.status === 'SOFTWARE_VERIFIED' ? 'good' : 'warn';
      modules[id].next = result.nextResultRu || modules[id].next;
    }
  }
  const domainMeta = {
    pytest_diagnostics:['Диагностика pytest','Ход выполнения, тайм-ауты и корректность диагностических отчётов.'],
    financial_ledger:['Финансовый реестр','Проводки, сверка, учёт и целостность финансовых контрактов.'],
    recovery:['Восстановление','Сбои, повторные попытки, аренды и восстановление выполнения.'],
    backup_restore:['Резервные копии','Снимки, проверка целостности и восстановление состояния.'],
    security_governance:['Безопасность и полномочия','Идентичность, авторизация и конституционные ограничения.'],
    execution_scheduler:['Планирование выполнения','Очереди, исполнители и диспетчеризация задач.'],
    events_commands:['События и команды','Командная шина, события и журналирование.'],
    registry_schema:['Реестры и схемы','Регистрация компонентов и согласованность схем.'],
    ci_release:['CI и релизы','Контракты сборок, регрессия и доказательства выпусков.'],
    audit_integrity:['Аудит и целостность','Проверка данных, валидация и прослеживаемость.'],
    runtime_kernel:['Ядро и среда исполнения','Жизненный цикл, движки и контракты Kernel Runner.'],
    education:['Образование','Образовательные процессы и учреждения.'],
    healthcare:['Здравоохранение','Программные контракты медицинских сервисов.'],
    simulation:['Моделирование','Контракты программных моделей и симуляции.'],
    transactions:['Транзакции','Фиксация операций и защита от повторного выполнения.'],
    cognition_learning:['Познание и обучение','Когнитивные процессы, память и обучение.'],
    society_governance:['Общество и управление','Социальные институты и модели управления.'],
    economy_resources:['Экономика и ресурсы','Ресурсные модели и экономические процессы.'],
    communication_persistence:['Связь и хранение','Обмен сообщениями и сохранение состояния.'],
    orchestration_control:['Оркестрация и контроль','Координация компонентов и управление процессами.'],
    simulation_agents:['Агенты моделирования','Агентные модели и сценарии взаимодействия.'],
    knowledge_culture:['Знания и культура','Программные модели знаний и культурных процессов.'],
    population_services:['Сервисы населения','Население и связанные программные сервисы.'],
    diagnostic_investigation:['Исследование отказов','Диагностические гипотезы и расследование сбоев.']
  };
  const contracts = [
    {id:'SP-IC-001',name:'Команда управления',from:'TrainOS',to:'Rail Systems',summary:'Ограниченное по времени исполнение команды с проверкой прав, состояния и подтверждением результата.',fields:['command_id: UUID','schema_version: 1','issued_at: RFC3339 UTC','ttl_ms: positive integer','principal_id: string','correlation_id: UUID','expected_revision: integer','payload: typed command'],checks:['Повтор command_id не создаёт повторный физический эффект.','Просроченная команда отклоняется до выполнения.','Несовпадение expected_revision требует повторной оценки.','Отсутствие подтверждения оставляет исход UNKNOWN; нужна сверка.'],module:'SP-RAIL'},
    {id:'SP-IC-002',name:'Интеллектуальное предложение',from:'AI / Cognition',to:'TrainOS',summary:'Проверяемое предложение с происхождением решения, ограничениями и отдельным допуском к исполнению.',fields:['proposal_id: UUID','model_version: string','context_ref: artifact URI','rationale: string','risk_class: enum','requested_action: typed proposal','operator_approval_ref: optional URI'],checks:['Предложение само по себе не даёт права управления.','Правила допуска и право вмешательства оператора проверяются отдельно.','Версия модели и контекст сохраняются в журнале.','При отказе модели доступен определённый безопасный режим.'],module:'SP-AI'},
    {id:'SP-IC-003',name:'Энергетическая телеметрия',from:'Energy',to:'TrainOS',summary:'Измерения с единицами, качеством и сроком актуальности для энергобаланса и режимов деградации.',fields:['event_id: UUID','source_id: string','observed_at: RFC3339 UTC','metric: registered name','value: number','unit: SI unit','quality: GOOD | SUSPECT | INVALID','max_age_ms: integer'],checks:['Устаревшее значение не считается текущим измерением.','Единица измерения обязательна и соответствует схеме метрики.','Разрыв связи явно отмечает качество данных.','Аварийная защита требует самостоятельной инженерной верификации.'],module:'SP-ENERGY'},
    {id:'SP-IC-004',name:'Авторизация и аудит',from:'Security',to:'Все подсистемы',summary:'Единый запрос доступа, проверка политики и неизменяемая ссылка на решение в журнале.',fields:['request_id: UUID','principal_id: string','resource: string','action: registered action','policy_version: string','decision: ALLOW | DENY','audit_ref: artifact URI'],checks:['Без явного разрешения запрос отклоняется.','Решение связано с конкретной версией политики.','Повышение полномочий требует отдельного разрешения.','Отказ журналирования не должен незаметно обходить контроль.'],module:'SP-SAFE'},
    {id:'SP-IC-005',name:'Логистическое задание',from:'TrainOS',to:'Logistics',summary:'Отслеживаемое задание на перемещение с идемпотентностью, подтверждением приёма и сверкой результата.',fields:['job_id: UUID','idempotency_key: string','inventory_ref: string','origin: location ID','destination: location ID','state: ACCEPTED | RUNNING | COMPLETED | UNKNOWN','operator_override: boolean'],checks:['Подтверждение приёма не означает завершение доставки.','Повтор задания не дублирует списание ресурсов.','Потеря связи переводит результат в явно неизвестный.','Ручное вмешательство и сверка запасов оставляют след аудита.'],module:'SP-LOG'},
    {id:'SP-IC-006',name:'Событие жизнеобеспечения',from:'Life Support',to:'TrainOS / Operations',summary:'Событие среды обитания с качеством измерения, уровнем серьёзности и подтверждением оператора.',fields:['alarm_id: UUID','sensor_id: string','observed_at: RFC3339 UTC','metric: registered name','value: number','unit: SI unit','severity: INFO | WARNING | CRITICAL','acknowledgement_ref: optional URI'],checks:['Подтверждение оператора не снимает причину аварийного события.','Пропавший датчик отличается от нормального значения.','Состояние защиты определяется независимыми инженерными требованиями.','Повторное событие связывается с исходной причиной.'],module:'SP-LIFE'}
  ];
  const defaults = [
    {id:'sp-priority-1',title:'Стабилизировать тестовую инфраструктуру TrainOS',module:'SP-SW',priority:'P0',description:'Воспроизводимая строгая регрессия, полный Kernel Runner и сохранённые журналы.',done:false},
    {id:'sp-priority-2',title:'Провести аудит функциональных Stage и требований',module:'SP-SW',priority:'P1',description:'Связать каждую область с требованиями, критериями приёмки и доказательствами.',done:false},
    {id:'sp-priority-3',title:'Сформировать единый реестр готовности',module:'SP-OPS',priority:'P1',description:'Для всех 9 подсистем указать артефакты, зависимости и недостающие доказательства.',done:false},
    {id:'sp-priority-4',title:'Определить интеграционные контракты',module:'SP-OPS',priority:'P1',description:'Согласовать интерфейсы TrainOS, AI, энергетики, транспорта и безопасности.',done:false},
    {id:'sp-priority-5',title:'Измерять подтверждённые результаты',module:'SP-OPS',priority:'P2',description:'Утвердить объём и веса до расчёта общего прогресса SnowPiercer.',done:false}
  ];
  const storageKey = 'snowpiercer.trainos.workspace.v1';
  let tasks;
  try {
    const saved=JSON.parse(localStorage.getItem(storageKey));
    tasks=Array.isArray(saved)&&saved.every(t=>typeof t.id==='string'&&typeof t.title==='string'&&modules[t.module]&&['P0','P1','P2'].includes(t.priority)&&typeof t.done==='boolean')?saved:structuredClone(defaults);
  } catch { tasks=structuredClone(defaults); }
  const workflowKey = 'snowpiercer.ecosystem.workflow.v1';
  let workflowState = G.initial(E), pendingTransition = null;
  try {
    const saved = JSON.parse(localStorage.getItem(workflowKey));
    if (G.validate(saved,E)) workflowState = saved;
  } catch { /* An invalid personal plan cannot grant a later stage. */ }
  let query='', filter='all', current='overview', toastTimer;
  const titleMap={overview:'Обзор системы',ecosystem:'Экосистема',domains:'Функциональные области',evidence:'Аудит и доказательства',contracts:'Интеграционные контракты',development:'Параллельное развитие',roadmap:'Дорожная карта',tasks:'Задачи'};
  const iconify=(root=document)=>root.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=icon(el.dataset.icon);});
  function notify(message) { const el=document.getElementById('toast');el.textContent=message;el.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{el.hidden=true;},4200); }
  function persist() { try {localStorage.setItem(storageKey,JSON.stringify(tasks));} catch {notify('Хранилище браузера недоступно. Экспортируйте отчёт, чтобы сохранить задачи.');} }
  function workflowPanel() {
    const assessment = G.assess(workflowState,E);
    return `<section class="workflow-panel"><div class="workflow-copy"><span class="eyebrow">${esc(E.iterationId)} · ЭТАП РАБОЧЕГО ПЛАНА</span><h2><span>${assessment.current.roman}</span> ${assessment.current.name}</h2><p>6 направлений развиваются параллельно. Переход сохраняет этап и историю в этом браузере.</p></div><div class="workflow-action"><button class="button lime next-stage-button" data-action="next-stage">${assessment.next?`Следующий этап: ${assessment.next.name}`:'План текущей итерации завершён'} ${icon('arrow')}</button><span>${assessment.allowed?'Критерии перехода выполнены для этой итерации':'Открыть критерии и недостающие доказательства'}</span></div></section>`;
  }
  function testSummary(result) {
    return `<span class="test-count">${result.tests.passed} passed</span>${result.tests.skipped?`<span class="skip-count">${result.tests.skipped} skipped</span>`:''}`;
  }
  function developmentCards() {
    return `<div class="development-grid">${E.modules.map(result=>{
      const meta=modules[result.moduleId];
      return `<article class="development-card"><div class="card-top"><span class="node-icon">${icon(meta.icon)}</span>${badge('Программный этап',result.status==='SOFTWARE_VERIFIED'?'good':'warn')}</div><h3>${meta.name}</h3><div class="stage-chain"><span>${esc(result.sourceStage)}</span><span>→</span><strong>${esc(result.targetStage)}</strong></div><p class="capability">${esc(result.capabilityRu)}</p><p>${esc(result.summaryRu)}</p><div class="development-tests">${testSummary(result)}<span>+${result.tests.added} новых</span></div><div class="development-links"><button class="text-link" data-development="${result.id}">Изменения и ограничения ↗</button><a class="text-link" href="${esc(result.artifact.path)}" download>${icon('download')}Исходники</a></div></article>`;
    }).join('')}</div>`;
  }
  function developmentStrip() {
    return `<div class="section-heading"><h2>Шесть параллельных направлений</h2><a class="text-link" href="#development">Изменения, проверки и исходники ↗</a></div><div class="parallel-strip">${E.modules.map(m=>`<button class="iteration-module" data-development="${m.id}"><span class="node-icon">${icon(modules[m.moduleId].icon)}</span><strong>${esc(modules[m.moduleId].name)}</strong><span class="iteration-stage">${esc(m.targetStage)}</span><span class="iteration-count">${m.tests.passed} passed${m.tests.skipped?` · ${m.tests.skipped} skipped`:''}</span></button>`).join('')}</div>`;
  }
  function developmentView() {
    const passed=E.modules.reduce((sum,m)=>sum+m.tests.passed,0);
    const skipped=E.modules.reduce((sum,m)=>sum+m.tests.skipped,0);
    const added=E.modules.reduce((sum,m)=>sum+m.tests.added,0);
    return `${header('Параллельное развитие','Шесть загруженных подсистем развиты независимо и проверены в общей итерации.')} ${workflowPanel()}<div class="iteration-metrics"><span><strong>${E.modules.length}</strong> программных направлений</span><span><strong>${passed}</strong> пройденных проверок</span><span><strong>${added}</strong> новых</span><span><strong>${skipped}</strong> пропущено по условиям среды</span></div><div class="inline-notice">${icon('info')}<span>Результаты относятся к программным моделям и границам API. Привилегированные проверки, физические испытания и эксплуатационная приёмка не подменяются успешной локальной регрессией. Security и Operations остаются самостоятельными направлениями с недостающими доказательствами.</span></div>${developmentCards()}<section class="panel integration-panel"><div class="panel-header"><div><h2>Общая проверка программных границ</h2><p>Единый контракт наблюдения и общий идентификатор прогона.</p></div>${badge(E.integration.status==='passed'?'6 / 6 probes прошли':'Не подтверждена',E.integration.status==='passed'?'good':'warn')}</div><div class="integration-copy"><code>${esc(E.integration.correlationId)}</code><p>Каждый probe вызывает реальный API своего модуля и проверяет допустимый и отказный сценарии. Это не обмен сообщениями между физическими подсистемами.</p><a class="text-link" href="subsystems/integration-report.json" target="_blank" rel="noopener">Открыть общий отчёт ↗</a></div></section><div class="downloads"><a class="download-card" href="evidence/TrainOS_Workspace.zip" download>${icon('download')}<span>Весь проект SnowPiercer<small>TrainOS, шесть подсистем, интерфейс и проверки</small></span><span>↗</span></a><a class="download-card" href="subsystems/development-register.json" download>${icon('file')}<span>Реестр этой итерации<small>Происхождение, требования и результаты</small></span><span>↗</span></a><button class="download-card" data-action="export">${icon('route')}<span>План и история переходов<small>Экспорт с вашими задачами</small></span><span>↗</span></button></div>`;
  }
  function developmentEvidence() {
    return `<section class="panel development-audit"><div class="panel-header"><div><h2>Новые проверки подсистем · 15 ноября 2026</h2><p>Полные доступные регрессии каждого направления; привилегированные пропуски указаны явно.</p></div><a class="text-link" href="#development">К изменениям ↗</a></div><div class="table-overflow"><table class="activity-table"><thead><tr><th>ПОДСИСТЕМА</th><th>НОВЫЙ ЭТАП</th><th>РЕГРЕССИЯ</th><th>СВИДЕТЕЛЬСТВО</th></tr></thead><tbody>${E.modules.map(m=>`<tr><td>${esc(modules[m.moduleId].name)}</td><td>${esc(m.targetStage)}</td><td>${testSummary(m)}</td><td><a class="text-link" href="${esc(m.reportPath)}" target="_blank" rel="noopener">Отчёт ↗</a></td></tr>`).join('')}</tbody></table></div></section>`;
  }
  function openDevelopment(id) {
    const result=E.modules.find(m=>m.id===id);if(!result)return;
    showDetail(modules[result.moduleId].name,result.sourceStage+' → '+result.targetStage,
      `<div class="development-tests">${testSummary(result)} ${badge('Эксплуатация: NO-GO','warn')}</div><div class="detail-section"><h3>${esc(result.capabilityRu)}</h3><p class="form-note">${esc(result.summaryRu)}</p></div><div class="detail-section"><h3>Подтверждённые требования</h3><ul>${result.requirements.map(r=>`<li><strong>${esc(r.id)}</strong> · ${esc(r.criterion)}<span class="source-path">${esc(r.evidence)}</span></li>`).join('')}</ul></div><div class="detail-section"><h3>Ограничения</h3><ul>${result.limits.map(value=>`<li>${esc(value)}</li>`).join('')}</ul></div><div class="detail-section"><h3>Исходный архив</h3><p class="form-note">${esc(result.sourceArchive.name)}</p><div class="code-block">SHA-256: ${esc(result.sourceArchive.sha256)}\nПроверка источника: ${esc(result.sourceIntegrity.summaryRu || result.sourceIntegrity.status)}</div></div><div class="detail-section detail-chip-list"><a class="button primary" href="${esc(result.artifact.path)}" download>${icon('download')}Скачать ${esc(result.targetStage)}</a><a class="button secondary" href="${esc(result.reportPath)}" target="_blank" rel="noopener">Полный отчёт ↗</a></div>`,result.moduleId);
  }
  function openStage() {
    const assessment=G.assess(workflowState,E);
    pendingTransition={expectedRevision:workflowState.revision,expectedStage:assessment.current.id,evidenceRevision:E.evidenceRevision};
    document.getElementById('stage-content').innerHTML=`<div class="dialog-heading"><div><span class="eyebrow">${esc(E.iterationId)} · РАБОЧИЙ ПЛАН</span><h2 id="stage-title">${assessment.next?`${assessment.current.roman} → ${assessment.next.roman}. ${assessment.next.name}`:'Текущий план завершён'}</h2></div><button class="icon-button" data-action="close-stage" aria-label="Закрыть">${icon('close')}</button></div><p class="detail-subtitle">Переход меняет этап рабочего плана для доступных материалов этой итерации. Он не запускает разработку на сервере и не подтверждает готовность всей экосистемы.</p><div class="stage-gates">${assessment.checks.map(check=>`<div class="stage-gate ${check.met?'met':'unmet'}"><span class="gate-symbol">${check.met?'✓':'○'}</span><div><strong>${esc(check.label)}</strong><p>${esc(check.detail)}</p></div></div>`).join('')}</div>${workflowState.history.length?`<div class="detail-section"><h3>История переходов</h3><ul>${workflowState.history.map(event=>`<li>${esc(G.stages.find(s=>s.id===event.from).name)} → ${esc(G.stages.find(s=>s.id===event.to).name)} · ${esc(new Intl.DateTimeFormat('ru-RU',{dateStyle:'short',timeStyle:'short',timeZone:'Europe/Minsk'}).format(new Date(event.at)))}</li>`).join('')}</ul></div>`:''}<div class="dialog-actions"><button class="button secondary" data-action="export-stage">${icon('download')}Скачать план</button>${assessment.next?`<button class="button primary" data-action="confirm-stage" ${assessment.allowed?'':'disabled'}>Перейти к этапу ${assessment.next.roman} ${icon('arrow')}</button>`:''}</div>${!assessment.allowed&&assessment.next?'<p class="form-note">Невыполненные критерии сохраняют текущий этап. Отметки задач не заменяют доказательства.</p>':''}`;
    document.getElementById('stage-dialog').showModal();
  }
  function confirmStage() {
    try {
      if(!pendingTransition)throw new Error('Откройте переход заново.');
      const saved=localStorage.getItem(workflowKey);
      const live=saved?JSON.parse(saved):workflowState;
      const next=G.advance(live,E,{...pendingTransition,at:new Date().toISOString()});
      localStorage.setItem(workflowKey,JSON.stringify(next));
      workflowState=next;pendingTransition=null;document.getElementById('stage-dialog').close();render();
      notify(`Этап ${G.stages[next.currentIndex].roman}: ${G.stages[next.currentIndex].name}. История сохранена в этом браузере.`);
    } catch(error) {notify('Переход не выполнен: '+error.message);}
  }
  function header(title,description,action='task') {
    return `<div class="page-head"><div><h1>${title}</h1><p>${description}</p></div><div class="head-actions"><button class="button secondary" data-action="export">${icon('download')}Экспорт отчёта</button>${action==='task'?`<button class="button primary" data-action="new-task">${icon('plus')}Новая задача</button>`:''}</div></div>`;
  }
  const toolbar=(placeholder,options=[])=>`<div class="view-toolbar"><label class="search">${icon('search')}<input type="search" id="view-search" aria-label="${esc(placeholder)}" placeholder="${esc(placeholder)}" value="${esc(query)}"></label><div class="filter-group" aria-label="Фильтры">${options.map(o=>`<button class="filter-button ${filter===o[0]?'active':''}" data-filter="${o[0]}" aria-pressed="${filter===o[0]}">${o[1]}</button>`).join('')}</div></div>`;
  function checkButton(t) {return `<button class="check-button" role="checkbox" aria-checked="${t.done}" aria-label="${esc((t.done?'Вернуть в работу: ':'Отметить выполненной: ')+t.title)}" data-toggle-task="${esc(t.id)}">${t.done?'✓':''}</button>`;}
  function priorities() {
    const open=tasks.filter(t=>!t.done).slice(0,5);
    return `<section class="panel"><div class="panel-header"><div><h2>Ближайшие приоритеты</h2><p>От стратегии — к подтверждённому результату</p></div><a class="text-link" href="#tasks">↗</a></div><div class="priority-list">${open.length?open.map(t=>`<div class="priority-item">${checkButton(t)}<div class="priority-copy"><strong>${esc(t.title)}</strong><div class="priority-meta"><span class="priority-chip">${esc(t.priority)}</span><span>${esc(modules[t.module].name)}</span></div></div></div>`).join(''):'<div class="empty-state">Все задачи личного плана выполнены.<p>Подтверждённая готовность оценивается отдельно.</p></div>'}</div><div class="priority-footer"><span>Личный план · в этом браузере</span><a class="text-link" href="#tasks">Все задачи →</a></div></section>`;
  }
  function diagram() {
    return `<section class="panel"><div class="panel-header"><div><h2>Архитектура экосистемы</h2><p>Единая система. Взаимосвязанные подсистемы.</p></div><a class="text-link" href="#ecosystem">Открыть реестр ↗</a></div><div class="ecosystem-canvas"><button class="diagram-root" data-module="SP-SW"><span class="node-icon">${icon('code')}</span><span class="node-label">TrainOS<small>Программное ядро · v101</small></span><span class="node-dot"></span></button><div class="branch-vertical"></div><div class="ecosystem-nodes">${Object.entries(modules).filter(([id])=>id!=='SP-SW').map(([id,m])=>`<button class="mini-node ${developed.has(id)?'software-developed':''}" data-module="${id}"><span class="node-topline"><span class="node-icon">${icon(m.icon)}</span><span></span></span><strong>${m.name==='Integration & Operations'?'Integration & Ops':m.name}</strong><small>${m.subtitle}</small></button>`).join('')}</div></div><div class="diagram-legend"><span><i class="legend-line"></i>Концептуальная связь</span><span><i class="legend-pending"></i>Требуется оценка</span></div></section>`;
  }
  function heroArt() {
    return `<div class="hero-art" aria-hidden="true"><svg viewBox="0 0 560 260" fill="none"><path d="m0 195 110-53 74 24 65-63 53 45 85-84 65 55 108-25v167H0z" fill="#dbe4ce"/><path d="m0 213 132-26 85 12 94-46 76 30 91-46 82 24v100H0z" fill="#cfdbc0"/><path d="m-15 232 590-70" stroke="#94aa7e" stroke-width="1.1"/><path d="m-15 238 590-70" stroke="#a0b58a" stroke-width="1.1"/><g transform="rotate(-6.7 280 180)"><path d="M40 170h401l40 22v10H40z" fill="#344b36"/><path d="M59 147h348l33 23H59z" fill="#f2f5e8" stroke="#667f52" stroke-width="1.2"/><path d="M408 148h36l31 23h-35z" fill="#e8eddb" stroke="#667f52" stroke-width="1.2"/><path d="M430 152h12l21 15h-31z" fill="#6d8559"/><path d="M43 169h382l26 27H43z" fill="#e9eedd" stroke="#667f52" stroke-width="1.2"/><path d="M43 185h396l9 10H43z" fill="#9db67f"/><path d="M58 158h38v14H58z M108 158h38v14h-38z M167 158h38v14h-38z M217 158h38v14h-38z M275 158h38v14h-38z M325 158h38v14h-38z M376 158h24l16 14h-40z" fill="#879e71"/><path d="M155 149v46 M263 149v46 M371 149v46" stroke="#6c8456" stroke-width="2.3"/><path d="M152 151v41 M260 151v41 M368 151v41" stroke="#d2dcc4" stroke-width="1.3"/><path d="M50 178h370" stroke="#c1d0af"/><path d="M444 179h16l10 8h-18z" fill="#728a5d"/><path d="M450 196h22" stroke="#c1cfaa" stroke-width="3"/><circle cx="77" cy="202" r="7" fill="#3c5037"/><circle cx="119" cy="202" r="7" fill="#3c5037"/><circle cx="185" cy="202" r="7" fill="#3c5037"/><circle cx="227" cy="202" r="7" fill="#3c5037"/><circle cx="293" cy="202" r="7" fill="#3c5037"/><circle cx="335" cy="202" r="7" fill="#3c5037"/><circle cx="396" cy="202" r="7" fill="#3c5037"/><circle cx="437" cy="202" r="7" fill="#3c5037"/><path d="M66 146v-5h60v5 M173 146v-5h60v5 M280 146v-5h60v5" stroke="#7c9464" stroke-width="1.4"/><path d="m205 140 10-12h24l-12 12" stroke="#7c9464" stroke-width="1.5"/></g><path d="M382 89v-25m-10 10 10-10 10 10" stroke="#9caf87"/><path d="m74 105 23-13 23 13-23 13-23-13z M97 118v19 M74 105v20l23 12 23-12v-20" stroke="#bdc9ab"/><circle cx="484" cy="81" r="3" fill="#abc091"/><circle cx="338" cy="40" r="2" fill="#b8c7a7"/><path d="M172 79h13 M178.5 72.5v13" stroke="#bdc9ab"/></svg></div>`;
  }
  function overview() {
    return `${header('Обзор системы','Всё, что нужно знать о SnowPiercer. В одном пространстве.')}<section class="hero"><div class="hero-copy"><span class="eyebrow">SNOWPIERCER ECOSYSTEM</span><h2>Большая система.<br>Проверяемый прогресс.</h2><p>От программного ядра до физической инфраструктуры —<br>строим единую интегрированную экосистему.</p><div class="hero-bottom"><span class="tag">TrainOS v101</span><span>Основа подключена. Движемся дальше.</span></div></div>${heroArt()}</section>
      ${workflowPanel()}<div class="stats"><div class="stat"><div class="stat-top"><span>Текущая версия TrainOS</span>${icon('code')}</div><div class="stat-value">v101<span class="version-tag">БАЗОВЫЙ АРХИВ</span></div><div class="stat-note"><span class="tiny-dot"></span>Целостность SHA-256 подтверждена</div></div><div class="stat"><div class="stat-top"><span>Функциональные области</span>${icon('layers')}</div><div class="stat-value">24</div><div class="stat-note">950 модулей в Kernel Runner</div></div><div class="stat"><div class="stat-top"><span>Подсистемы SnowPiercer</span>${icon('ecosystem')}</div><div class="stat-value">9</div><div class="stat-note">Единый реестр зависимостей</div></div><div class="stat"><div class="stat-top"><span>Готовность к эксплуатации</span>${icon('shield')}</div><div class="stat-value no-go">NO-GO</div><div class="stat-note"><span class="status-mini"><span class="tiny-dot"></span>Есть незакрытые критерии</span></div></div></div>
      ${developmentStrip()}<div class="dashboard-grid">${diagram()}${priorities()}</div><div class="section-heading"><h2>Подтверждённые результаты</h2><a class="text-link" href="#evidence">Все доказательства ↗</a></div><section class="panel table-overflow"><table class="activity-table"><thead><tr><th>ПРОВЕРКА</th><th>ИСТОЧНИК</th><th>РЕЗУЛЬТАТ</th><th>ПОДРОБНОСТИ</th></tr></thead><tbody><tr><td>${icon('shield')}Целостность исходного архива</td><td>Локальная проверка</td><td>${badge('6 720 совпадений','good',true)}</td><td><button class="text-link" data-action="sources">SHA-256 ↗</button></td></tr><tr><td>${icon('check')}Полная строгая регрессия</td><td>${V.status==='passed'?'Проверка 14.11 · Python 3.13':'Отчёт v101'}</td><td>${badge('1 487 passed','good',true)}</td><td><a class="text-link" href="#evidence">Открыть отчёт ↗</a></td></tr><tr><td>${icon('clock')}Общий прогресс SnowPiercer</td><td>Реестр экосистемы</td><td>${badge('Не рассчитан','neutral')}</td><td><a class="text-link" href="#ecosystem">Критерии оценки ↗</a></td></tr></tbody></table></section>`;
  }
  function ecosystem() {
    return `${header('Экосистема SnowPiercer','9 подсистем. Общая архитектура и независимые критерии готовности.')}<div class="inline-notice">${icon('info')}<span>Общий процент готовности не рассчитан. Для расчёта нужны утверждённый объём, веса, критерии приёмки и связанные с ними доказательства. Программные тесты не подтверждают готовность оборудования.</span></div>${toolbar('Найти подсистему…',[['all','Все подсистемы'],['active','В разработке'],['pending','Требуется оценка']])}<div class="cards-grid">${D.modules.map(m=>{const meta=modules[m.id];return `<button class="module-card filter-item" data-module="${m.id}" data-search="${esc((meta.name+' '+meta.subtitle+' '+m.id).toLowerCase())}" data-kind="${m.id==='SP-SW'||developed.has(m.id)?'active':'pending'}"><div class="card-top"><span class="node-icon">${icon(meta.icon)}</span><span class="card-code">${m.id}</span></div><h3>${meta.name}</h3><p>${meta.subtitle}</p><div class="card-bottom">${badge(meta.status,meta.kind||'neutral')}<span class="arrow">↗</span></div></button>`;}).join('')}</div><p class="local-note">Реестр обновлён 15 ноября 2026 года. Исходные зависимости сохранены из baseline v7; новые программные результаты шести подсистем приведены в разделе развития. Нажмите на подсистему, чтобы увидеть зависимости и требования к доказательствам.</p>`;
  }
  function domains() {
    const physical=D.domains.reduce((s,d)=>s+d.physicalFiles,0);
    return `${header('Функциональные области','24 области тестирования · 950 модулей в реестре Kernel Runner.')}<div class="inline-notice">${icon('layers')}<span>Функциональная классификация охватывает все 950 модулей Runner. Физически перенесено в tests/domains: ${physical}. Остальные сохраняют исторические пути. Ещё 5 вспомогательных тестовых модулей выполняются полной регрессией.</span></div>${toolbar('Найти область или идентификатор…',[['all','Все 24 области'],['migrated','Есть новые пути'],['legacy','Исторические пути']])}<div class="cards-grid">${D.domains.map(d=>{const [title,desc]=domainMeta[d.id]||[d.id,''];return `<button class="domain-card filter-item" data-domain="${d.id}" data-search="${esc((d.id+' '+title+' '+desc).toLowerCase())}" data-kind="${d.physicalFiles?'migrated':'legacy'}"><div class="card-top"><span class="node-icon">${icon(d.id==='financial_ledger'?'file':d.id==='recovery'?'route':d.id==='runtime_kernel'?'code':'layers')}</span>${badge(d.physicalFiles?'Гибридное размещение':'Исторические пути',d.physicalFiles?'good':'neutral')}</div><h3>${title}</h3><span class="domain-code">${d.id}</span><p>${desc}</p><div class="domain-numbers"><span><strong>${d.files.length}</strong> модулей</span><span>${d.physicalFiles} в tests/domains</span></div><div class="migration-bar" aria-label="${d.physicalFiles} из ${d.files.length} файлов физически перенесено"><span style="width:${100*d.physicalFiles/d.files.length}%"></span></div><span class="domain-foot">Показатель размещения файлов</span></button>`;}).join('')}</div>`;
  }
  function evidence() {
    const localPassed=V.status==='passed',kernelPassed=V.kernel?.status==='passed';
    return `${header('Аудит и доказательства','Каждый вывод связан с источником. Архивные и текущие проверки показаны отдельно.','none')}${developmentEvidence()}<div class="evidence-summary"><section class="evidence-spotlight"><span class="eyebrow">ПОЛНАЯ СТРОГАЯ РЕГРЕССИЯ</span><h2><span class="evidence-number">1 487</span><span class="evidence-sub">тестов прошли</span></h2>${badge(localPassed?'Проверено 14 ноября 2026':'По отчёту архива v101','good',true)}<p>${localPassed?`Python ${esc(V.python)} · pytest ${esc(V.pytest)} · ${esc(V.full?.duration_seconds)} сек. ${esc(V.environmentNote)}`:'Архив содержит успешный финальный прогон. Локальное подтверждение показывается после завершения проверки.'}</p></section><section class="evidence-spotlight"><span class="eyebrow">РЕШЕНИЕ ИСХОДНОГО РЕЛИЗА</span><div class="large-decision">BLOCKED / NO-GO</div>${badge('Готовность к эксплуатации не подтверждена','warn')}<p>Архив v101 сохраняет консервативное решение. Внешние платежи, эксплуатация физических подсистем и независимая приёмка не подтверждены текущими программными проверками.</p></section></div>
      <section class="panel table-overflow"><table class="activity-table evidence-table"><thead><tr><th>ПРОВЕРКА И ОБЛАСТЬ</th><th>ПРОИСХОЖДЕНИЕ</th><th>РЕЗУЛЬТАТ</th><th>ДОКАЗАТЕЛЬСТВО</th></tr></thead><tbody>
      <tr><td>SHA-256-манифест<span class="source-path">Все исходные файлы, кроме самого манифеста</span></td><td>Текущая проверка</td><td>${badge('6 720 / 6 720','good',true)}</td><td><a class="text-link" href="evidence/SHA256_MANIFEST_V101.json" target="_blank" rel="noopener">Манифест ↗</a></td></tr>
      <tr><td>Строгая полная регрессия<span class="source-path">ResourceWarning, DeprecationWarning, PytestUnraisableExceptionWarning → error</span></td><td>Отчёт архива v101</td><td>${badge('1 487 passed','good',true)}</td><td><a class="text-link" href="evidence/RELEASE_V101_VALIDATION.json" target="_blank" rel="noopener">Отчёт v101 ↗</a></td></tr>
      <tr><td>Строгая полная регрессия<span class="source-path">Python 3.13 · восстановленные права .sh · Linux subreaper</span></td><td>Проверка 14.11.2026</td><td>${badge(localPassed?'1 487 passed':'Не завершена',localPassed?'good':'neutral',localPassed)}</td><td>${localPassed?'<a class="text-link" href="evidence/local-verification.json" target="_blank" rel="noopener">Локальный отчёт ↗</a>':'Ожидается'}</td></tr>
      <tr><td>Kernel Runner · обычный режим<span class="source-path">Отдельный pytest для каждого файла, TRAINOS_KERNEL_BATCH не задан</span></td><td>Отчёт архива v101</td><td>${badge('Прерван · exit 143','warn')}</td><td><a class="text-link" href="evidence/RELEASE_V101_NOTES.md" target="_blank" rel="noopener">Ограничения v101 ↗</a></td></tr>
      <tr><td>Kernel Runner · обычный режим<span class="source-path">Сохранённый прогон 14.11.2026 всех настроенных областей</span></td><td>Проверка 14.11.2026</td><td>${badge(kernelPassed?'24 области прошли':V.kernel?.status==='failed'?'Есть сбой':'Не подтверждён',kernelPassed?'good':'neutral',kernelPassed)}</td><td>${V.kernel?'<a class="text-link" href="evidence/kernel-default.json" target="_blank" rel="noopener">Результат ↗</a>':'Нет завершённого отчёта'}</td></tr>
      <tr><td>Kernel Runner · пакетный режим<span class="source-path">Опциональный TRAINOS_KERNEL_BATCH=1</span></td><td>Отчёт архива v101</td><td>${badge('Все области прошли','good',true)}</td><td><a class="text-link" href="evidence/RELEASE_V101_VALIDATION.json" target="_blank" rel="noopener">Отчёт v101 ↗</a></td></tr>
      <tr><td>Внешний платёжный sandbox<span class="source-path">Требуется независимая проверка провайдера</span></td><td>Нет подтверждения</td><td>${badge('NO-GO','warn')}</td><td><button class="text-link" data-module="SP-SW">Критерии ↗</button></td></tr>
      <tr><td>Готовность физических подсистем<span class="source-path">Инженерные, моделирующие и физические испытания</span></td><td>Требуются доказательства</td><td>${badge('Не оценена','neutral')}</td><td><a class="text-link" href="#ecosystem">Реестр ↗</a></td></tr></tbody></table></section>
      <div class="downloads"><a class="download-card" href="evidence/TrainOS_Workspace.zip" download>${icon('download')}<span>Полный проект SnowPiercer<small>TrainOS, шесть подсистем и инструкция · ZIP</small></span><span>↗</span></a><a class="download-card" href="evidence/baseline-v7.json" download>${icon('ecosystem')}<span>Реестр экосистемы<small>Исходный baseline v7 · JSON</small></span><span>↗</span></a><button class="download-card" data-action="export">${icon('file')}<span>Текущий отчёт<small>Источники, проверки и ваши задачи</small></span><span>↗</span></button></div><p class="local-note">Успешный программный тест подтверждает только проверенный контракт в указанной среде. Итоговый процент SnowPiercer остаётся неопределённым. История первоначальных сбоев и настройки воспроизводимости сохранены в локальных материалах.</p>`;
  }
  function contractView() {
    return `${header('Интеграционные контракты','Общие границы взаимодействия TrainOS и подсистем SnowPiercer.')}<div class="inline-notice">${icon('contracts')}<span>6 проектных предложений для этапа архитектуры. Эти общесистемные проекты созданы на основе вашего плана; они ещё не согласованы и не подключены к оборудованию; реализованные программные границы перечислены в развитии.</span></div>${toolbar('Найти контракт или подсистему…')}<div class="contract-list">${contracts.map(c=>`<button class="contract-card filter-item" data-contract="${c.id}" data-search="${esc((c.id+' '+c.name+' '+c.from+' '+c.to).toLowerCase())}" data-kind="all"><div class="card-top"><span class="card-code">${c.id}</span>${badge('Проект · v0.1','draft')}</div><div class="contract-route">${esc(c.from)} ${icon('arrow')} ${esc(c.to)}</div><h3>${c.name}</h3><p>${c.summary}</p><div class="contract-meta"><span>${c.fields.length} полей · ${c.checks.length} критерия проверки</span><span>Открыть схему ↗</span></div></button>`).join('')}</div>`;
  }
  function roadmap() {
    const steps=[['I','Инвентаризация','Полный реестр модулей, зависимостей, требований и доказательств.','В работе','good'],['II','Архитектура','Интерфейсы подсистем, единые стандарты и интеграционные контракты.','Подготовлены проекты','draft'],['III','Разработка','Программные и аппаратные компоненты с критериями приёмки.','TrainOS в разработке','good'],['IV','Моделирование','Цифровые двойники, сценарии и анализ отказов.','Нужны доказательства','neutral'],['V','Испытания','Функциональные, интеграционные и безопасностные проверки.','ПО: есть результаты','good'],['VI','Интеграция','Объединение TrainOS с физическими подсистемами.','Не оценена','neutral'],['VII','Эксплуатация','Подтверждённая готовность, мониторинг и обслуживание.','NO-GO','warn'],['VIII','Развитие','Новые возможности и расширение экосистемы.','Долгосрочный этап','neutral']];
    return `${header('Дорожная карта','Долгосрочный путь от инвентаризации до непрерывного развития.')}${workflowPanel()}<div class="inline-notice">${icon('route')}<span>Этапы могут выполняться параллельно. Проектирование энергетики, транспорта, AI и других подсистем не требует полного завершения TrainOS. Календарные сроки и общий процент пока не утверждены.</span></div><div class="roadmap-list">${steps.map((s,index)=>`<article class="roadmap-step ${index===workflowState.currentIndex?'current-stage':''}"><span class="roadmap-roman">${s[0]}</span><div><h3>${s[1]}</h3><small>${index===workflowState.currentIndex?'ТЕКУЩИЙ РАБОЧИЙ ЭТАП':'ЭТАП '+s[0]+' · SNOWPIERCER'}</small></div><p>${s[2]}</p>${badge(s[3],s[4])}</article>`).join('')}</div><p class="roadmap-bottom">Состояния этапов описывают имеющиеся материалы: программная разработка и тесты ведутся, физическая приёмка не подтверждена. План не задаёт обещанных дат готовности.</p>`;
  }
  function tasksView() {
    return `${header('Задачи','Личный план работ и критерии завершения.')}<div class="view-toolbar"><div class="tasks-summary"><span><strong>${tasks.filter(t=>!t.done).length}</strong> в работе</span><span><strong>${tasks.filter(t=>t.done).length}</strong> выполнено</span><span><strong>${tasks.filter(t=>!t.done&&t.priority==='P0').length}</strong> критических</span></div><div class="filter-group"><button class="filter-button ${filter==='all'?'active':''}" data-filter="all" aria-pressed="${filter==='all'}">Все задачи</button><button class="filter-button ${filter==='open'?'active':''}" data-filter="open" aria-pressed="${filter==='open'}">В работе</button><button class="filter-button ${filter==='done'?'active':''}" data-filter="done" aria-pressed="${filter==='done'}">Выполненные</button></div></div><label class="search" style="margin-bottom:18px">${icon('search')}<input type="search" id="view-search" aria-label="Найти задачу" placeholder="Найти задачу…" value="${esc(query)}"></label><section class="panel table-overflow"><table class="activity-table task-table"><thead><tr><th>ЗАДАЧА И КРИТЕРИЙ ЗАВЕРШЕНИЯ</th><th>ПОДСИСТЕМА</th><th>ПРИОРИТЕТ</th><th>СТАТУС</th><th></th></tr></thead><tbody>${[...tasks].sort((a,b)=>Number(a.done)-Number(b.done)||a.priority.localeCompare(b.priority)).map(t=>`<tr class="filter-item" data-search="${esc((t.title+' '+(t.description||'')+' '+modules[t.module].name).toLowerCase())}" data-kind="${t.done?'done':'open'}"><td><div class="task-title ${t.done?'done':''}">${checkButton(t)}<div><strong>${esc(t.title)}</strong>${t.description?`<p>${esc(t.description)}</p>`:''}</div></div></td><td>${esc(modules[t.module].name)}</td><td><span class="priority-chip">${t.priority}</span></td><td>${badge(t.done?'Выполнена':'В работе',t.done?'good':'neutral')}</td><td>${t.id.startsWith('custom-')?`<button class="icon-button" aria-label="Удалить задачу ${esc(t.title)}" data-delete-task="${esc(t.id)}">${icon('trash')}</button>`:''}</td></tr>`).join('')}</tbody></table></section><p class="local-note">Задачи хранятся только в этом браузере. Экспорт отчёта включает их текущее состояние. Личная отметка о завершении не является доказательством готовности подсистемы.</p>`;
  }
  function filterItems() {
    let visible=0;
    document.querySelectorAll('.filter-item').forEach(el=>{const show=(!query||el.dataset.search.includes(query.toLowerCase().trim()))&&(filter==='all'||el.dataset.kind===filter);el.hidden=!show;if(show)visible++;});
    document.getElementById('filter-empty')?.remove();
    if(!visible&&['domains','ecosystem','contracts','tasks'].includes(current)){const el=document.createElement('div');el.id='filter-empty';el.className='empty-state';el.innerHTML=icon('search')+'Ничего не найдено<p>Попробуйте изменить запрос или фильтр.</p>';page.appendChild(el);}
  }
  function closeMenu() {document.getElementById('sidebar').classList.remove('open');document.querySelector('.sidebar-backdrop').hidden=true;document.querySelector('[data-action="menu"]').setAttribute('aria-expanded','false');}
  function render() {
    document.title=titleMap[current]+' — TrainOS';
    document.getElementById('breadcrumb-current').textContent=titleMap[current];
    document.querySelectorAll('[data-nav]').forEach(el=>{const selected=el.dataset.nav===current;el.classList.toggle('active',selected);if(selected)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
    document.querySelectorAll('.task-count').forEach(el=>el.textContent=String(tasks.filter(t=>!t.done).length));
    page.innerHTML=({overview,ecosystem,domains,evidence,development:developmentView,contracts:contractView,roadmap,tasks:tasksView}[current])();
    iconify(page);filterItems();closeMenu();
  }
  function route() {const next=location.hash.slice(1);current=titleMap[next]?next:'overview';query='';filter='all';render();window.scrollTo?.(0,0);}
  function showDetail(title,subtitle,body,eyebrow='SNOWPIERCER') {
    const dialog=document.getElementById('detail-dialog');
    document.getElementById('detail-content').innerHTML=`<div class="dialog-heading"><div><span class="eyebrow">${esc(eyebrow)}</span><h2 id="detail-title">${esc(title)}</h2></div><button class="icon-button" aria-label="Закрыть" data-action="close-detail">${icon('close')}</button></div><p class="detail-subtitle">${esc(subtitle)}</p>${body}`;
    if(!dialog.open)dialog.showModal();
  }
  function openModule(id) {
    const original=D.modules.find(m=>m.id===id),meta=modules[id];if(!original||!meta)return;
    showDetail(meta.name,meta.subtitle,`${badge(meta.status,meta.kind||'neutral')}${developed.has(id)?`<div class="detail-section"><h3>Новый программный этап</h3><p class="form-note">${esc(developed.get(id).capabilityRu)}</p><div class="development-tests">${testSummary(developed.get(id))}</div><button class="text-link" data-development="${developed.get(id).id}">Изменения, исходники и ограничения ↗</button></div>`:''}<div class="detail-section"><h3>Следующий подтверждённый результат</h3><p class="form-note">${meta.next}</p></div><div class="detail-section"><h3>Артефакты из исходного реестра</h3><ul>${original.deliverables.map(v=>`<li>${esc(v)}</li>`).join('')}</ul></div><div class="detail-section"><h3>Требуемые доказательства приёмки</h3><ul>${original.acceptance_evidence_required.map(v=>`<li>${esc(v)}</li>`).join('')}</ul></div><div class="detail-section"><h3>Зависимости</h3><div class="detail-chip-list">${original.dependencies.length?original.dependencies.map(id=>`<span class="detail-chip">${esc(modules[id]?.name||id)}</span>`).join(''):'<span class="form-note">В исходном baseline зависимости не перечислены.</span>'}</div></div><div class="detail-section"><h3>Критические критерии</h3><ul>${original.critical_gates.map(v=>`<li>${esc(v)}</li>`).join('')}</ul></div><div class="detail-section"><div class="inline-notice">${icon('info')}<span>Готовность не оценена в процентах. Наличие исходного кода или перечня артефактов не означает приёмку.</span></div><a class="text-link" href="evidence/baseline-v7.json" target="_blank" rel="noopener">Исходный baseline v7 · 28.10.2026 ↗</a></div>`,id);
  }
  function openDomain(id) {
    const d=D.domains.find(d=>d.id===id);if(!d)return;
    showDetail(domainMeta[id]?.[0]||id,domainMeta[id]?.[1]||'',`<div class="detail-chip-list"><span class="detail-chip">${d.files.length} тестовых модулей</span><span class="detail-chip">${d.physicalFiles} в tests/domains</span></div><div class="detail-section"><h3>Аудит требований</h3><p class="form-note">Привязка области к утверждённым системным требованиям и критериям приёмки ещё не выполнена в этом рабочем пространстве. Список ниже подтверждает регистрацию файлов.</p></div><div class="detail-section"><h3>Файлы в реестре Kernel Runner</h3><div class="source-file-list">${d.files.map(p=>`<div>${esc(p)}</div>`).join('')}</div></div><div class="detail-section"><h3>Воспроизводимая проверка области</h3><div class="code-block">python -m pytest -q -W error::ResourceWarning -W error::DeprecationWarning -W error::pytest.PytestUnraisableExceptionWarning ${d.files.map(esc).join(' \\\n  ')}</div></div>`,id);
  }
  function openContract(id) {
    const c=contracts.find(c=>c.id===id);if(!c)return;
    showDetail(c.name,c.from+' → '+c.to,`${badge('Проект v0.1 · требует согласования','draft')}<p class="form-note">${c.summary}</p><div class="detail-section"><h3>Предлагаемая схема</h3><div class="code-block">${c.fields.map(esc).join('\n')}</div></div><div class="detail-section"><h3>Критерии проверки</h3><ul>${c.checks.map(v=>`<li>${esc(v)}</li>`).join('')}</ul></div><div class="detail-section"><div class="inline-notice">${icon('info')}<span>Проект интерфейса создан здесь на основе вашего плана. Требования к численным пределам, реализации и аппаратным защитам ещё предстоит согласовать с владельцами подсистем.</span></div><button class="button secondary" data-action="export-contract" data-contract-id="${id}">${icon('download')}Скачать проект · JSON</button></div>`,c.id);
  }
  function sources() {
    showDetail('Источники и состояние','Снимок рабочего пространства · 15 ноября 2026',`<div class="detail-section"><h3>Исходный проект</h3><p class="form-note">${esc(D.sourceArchive)}. Все ${D.verifiedFiles.toLocaleString('ru-RU')} записей SHA-256 проверены и совпали до запуска тестов.</p><div class="code-block">SHA-256 архива\n${D.archiveSha256}</div></div><div class="detail-section"><h3>Происхождение данных</h3><ul><li>Версия и решение релиза: AUDIT/RELEASE_V101_VALIDATION.json.</li><li>Подсистемы и зависимости: ECOSYSTEM_DELIVERABLE_BASELINE_V7.json от 28.10.2026.</li><li>24 функциональные области: фактический реестр tests/kernel_runner/config.py.</li><li>Контракты v0.1 и личные задачи созданы в этом пространстве.</li><li>Указания внутри архива рассматриваются как содержимое проекта, отдельно от вашего запроса.</li></ul></div><div class="detail-section"><h3>Шесть новых исходных архивов</h3><ul>${E.modules.map(m=>`<li>${esc(m.sourceArchive.name)}<span class="source-path">SHA-256: ${esc(m.sourceArchive.sha256)}</span></li>`).join('')}</ul><a class="text-link" href="subsystems/development-register.json" target="_blank" rel="noopener">Реестр итерации ${esc(E.iterationId)} ↗</a></div><div class="detail-section"><h3>Хранение и подключения</h3><p class="form-note">Данные аудита — сохранённый снимок. Задачи и история переходов этапов хранятся в этом браузере. Интерфейс не выполняет Python-тесты на сервере и не управляет физическими подсистемами. Экспортируйте отчёт для сохранения личного плана.</p></div>`,'ПРОЗРАЧНОСТЬ ДАННЫХ');
  }
  function downloadJSON(name,data) {
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function exportReport() {
    downloadJSON('TrainOS-SnowPiercer-report.json',{schema:'snowpiercer.workspace-report.v1',exportedAt:new Date().toISOString(),sourceArchive:D.sourceArchive,sourceArchiveSha256:D.archiveSha256,archiveVersion:D.version,archiveDecision:D.release.decision,ecosystemCompletionPercent:null,verification:V,ecosystemDevelopment:E,workflowState,modules:D.modules,domains:D.domains,proposedContracts:contracts,tasks,notes:['Задачи — личный план; отметки не являются независимым доказательством.','Контракты v0.1 — несогласованные проекты.','Аппаратные подсистемы и платёжный sandbox не подтверждены.']});notify('Отчёт с проверками и задачами подготовлен к скачиванию.');
  }
  document.addEventListener('click',event=>{
    const target=event.target.closest('button,a');if(!target)return;
    if(target.dataset.development){openDevelopment(target.dataset.development);return;}
    if(target.dataset.module){openModule(target.dataset.module);return;}
    if(target.dataset.domain){openDomain(target.dataset.domain);return;}
    if(target.dataset.contract){openContract(target.dataset.contract);return;}
    if(target.dataset.toggleTask){const task=tasks.find(t=>t.id===target.dataset.toggleTask);if(task){task.done=!task.done;persist();render();notify(task.done?'Задача отмечена выполненной в личном плане.':'Задача возвращена в работу.');}return;}
    if(target.dataset.deleteTask){tasks=tasks.filter(t=>t.id!==target.dataset.deleteTask);persist();render();notify('Задача удалена из личного плана.');return;}
    if(target.dataset.filter){filter=target.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>{b.classList.toggle('active',b.dataset.filter===filter);b.setAttribute('aria-pressed',String(b.dataset.filter===filter));});filterItems();return;}
    switch(target.dataset.action){
      case 'next-stage':openStage();break;
      case 'close-stage':pendingTransition=null;document.getElementById('stage-dialog').close();break;
      case 'confirm-stage':confirmStage();break;
      case 'export-stage':downloadJSON(E.iterationId+'-stage-plan.json',{schema:'snowpiercer.stage-plan.v1',exportedAt:new Date().toISOString(),workflowState,assessment:G.assess(workflowState,E),evidenceRevision:E.evidenceRevision,operationalReady:false,ecosystemCompletionPercent:null});notify('План этапа и история переходов подготовлены к скачиванию.');break;
      case 'export':exportReport();break;
      case 'sources':sources();break;
      case 'new-task':document.getElementById('task-dialog').showModal();break;
      case 'close-task':document.getElementById('task-dialog').close();break;
      case 'close-detail':document.getElementById('detail-dialog').close();break;
      case 'export-contract':downloadJSON(target.dataset.contractId+'.json',{schema:'snowpiercer.integration-proposal.v0.1',status:'DRAFT_NOT_ACCEPTED',contract:contracts.find(c=>c.id===target.dataset.contractId)});notify('Проект контракта подготовлен к скачиванию.');break;
      case 'menu':{const open=document.getElementById('sidebar').classList.toggle('open');document.querySelector('.sidebar-backdrop').hidden=!open;target.setAttribute('aria-expanded',String(open));break;}
    }
  });
  document.querySelector('.sidebar-backdrop').addEventListener('click',closeMenu);
  document.addEventListener('keydown',event=>{if(event.key==='Escape')closeMenu();});
  document.addEventListener('input',event=>{if(event.target.id==='view-search'){query=event.target.value;filterItems();}});
  document.getElementById('task-form').addEventListener('submit',event=>{
    event.preventDefault();const form=event.target;const f=new FormData(form);const title=String(f.get('title')||'').trim();if(!title){form.elements.title.setCustomValidity('Введите название задачи.');form.elements.title.reportValidity();return;}form.elements.title.setCustomValidity('');
    const module=String(f.get('module'));if(!modules[module])return;
    tasks.push({id:'custom-'+(window.crypto?.randomUUID?.()||Date.now().toString(36)),title:title.slice(0,180),module,priority:['P0','P1','P2'].includes(String(f.get('priority')))?String(f.get('priority')):'P2',description:String(f.get('description')||'').trim().slice(0,1000),done:false});persist();form.reset();document.getElementById('task-dialog').close();if(current==='tasks')render();else location.hash='tasks';notify('Задача добавлена в личный план.');
  });
  document.querySelector('#task-form [name="title"]').addEventListener('input',event=>event.target.setCustomValidity(''));
  document.getElementById('task-module').innerHTML=Object.entries(modules).map(([id,m])=>`<option value="${id}">${m.name}</option>`).join('');
  window.addEventListener('hashchange',route);
  window.addEventListener('storage',event=>{
    if(event.key!==workflowKey)return;
    try {
      const updated=event.newValue?JSON.parse(event.newValue):G.initial(E);
      if(!G.validate(updated,E))throw new Error('Invalid stage history');
      workflowState=updated;pendingTransition=null;document.getElementById('stage-dialog').close();render();
      notify('Этап рабочего плана обновлён в другой вкладке.');
    } catch {notify('Сохранённый этап повреждён. Текущий план не изменён.');}
  });
  iconify();route();
})();
