/* 日文学术 PDF 工作台：任务控制台 / 渠道矩阵 / 诊断
 * P0 只做可观测与可恢复；文献库、质量复核、报告、评测在 P1/P2 接入。
 */
var S = {
    route: 'overview', jobs: [], channels: {}, selectedJob: '', selectedDoc: '',
    q: '', filter: 'all', diag: null, online: false, library: [], review: [], reviewCounts: {},
    reviewFilter: 'needs_manual_review', reviewDoc: null, libQ: '', libFilter: '', libLoading: false,
    evalReports: [], evalSel: '', indexStatus: null, doc: null, loading: false
};
var toastTimer;

function $(id) { return document.getElementById(id); }
function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
        return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c];
    });
}
function pad(n) { return n < 10 ? '0' + n : '' + n; }
function clock(ts) {
    if (!ts) return '-';
    var d = new Date(ts * 1000);
    return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
}
function duration(sec) {
    sec = Math.max(0, parseInt(sec || 0, 10));
    var h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
    return h ? h + '时' + m + '分' + s + '秒' : (m ? m + '分' + s + '秒' : s + '秒');
}
function toast(msg, error) {
    clearTimeout(toastTimer);
    var t = $('toast');
    t.textContent = msg;
    t.className = 'toast show' + (error ? ' err' : '');
    toastTimer = setTimeout(function () { t.className = 'toast'; }, 3600);
}
function api(url, opts) {
    return fetch(url, opts || {}).then(function (r) {
        return r.text().then(function (text) {
            var data;
            try { data = text ? JSON.parse(text) : {}; } catch (e) { data = { raw: text }; }
            if (!r.ok) throw new Error((data && (data.err || data.msg)) || ('HTTP ' + r.status));
            return data;
        });
    });
}
function stateInfo(state) {
    return ({
        '运行中': ['run', '运行中'], '排队中': ['que', '排队中'], done: ['ok', '已完成'],
        degraded: ['warn', '部分异常'], error: ['err', '失败']
    })[state] || ['que', state || '未知'];
}
var STATUS = {
    waiting: ['等待', 'que'], running: ['运行', 'run'], done: ['完成', 'ok'],
    warning: ['异常', 'warn'], error: ['失败', 'err'], skipped: ['未执行', 'skip']
};
var CHANNEL_LABELS = { mineru: 'MinerU', dots: 'dots.ocr', paddle: 'PaddleOCR' };
var FLAG_LABELS = {
    title_missing: '题名缺失', title_suspect: '题名存疑', title_repaired: '题名修正',
    authors_missing: '作者缺失', authors_from_raw: '作者来自原文', authors_filtered: '作者过滤',
    journal_missing: '期刊缺失', journal_suspect: '期刊存疑', year_missing: '年份缺失',
    pages_suspect: '页码存疑', references_incomplete: '参考文献不全',
    citations_unresolved: '引文未解析', citations_missing: '引文缺失',
    abstract_missing: '摘要缺失', abstract_from_en: '英文摘要回填',
    composite_document: '合刊/多篇', needs_manual_review: '需人工复核',
    metadata_missing: '元数据缺失', index_missing: '结果页缺失'
};
function flagLabel(f) { return FLAG_LABELS[f] || f; }
function flagTags(flags, max) {
    flags = flags || [];
    max = max || 4;
    return flags.slice(0, max).map(function (f) {
        return '<span class="tag ' + (/missing|unresolved|suspect|incomplete/.test(f) ? 'warn' : '') + '">' + esc(flagLabel(f)) + '</span>';
    }).join('') + (flags.length > max ? '<span class="tag">+' + (flags.length - max) + '</span>' : '');
}
var PIPELINE = [
    ['render', '页图准备'], ['acquire', '渠道解析'], ['adapt', '结果适配'],
    ['unify', '合并归一化'], ['vreorder', '竖排重排'], ['metadata', '元数据'],
    ['vertical', '竖排题名'], ['normalize', '字段规范化'],
    ['entities', '实体抽取'], ['publish', '结果发布']
];

function activeJobs() {
    return S.jobs.filter(function (j) { return j.state === '运行中' || j.state === '排队中'; });
}
function selectedJob() {
    for (var i = 0; i < S.jobs.length; i++) if (S.jobs[i].id === S.selectedJob) return S.jobs[i];
    return null;
}
function isEditing() {
    var a = document.activeElement;
    return a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName);
}

/* ---------------- 全局刷新 ---------------- */
function tick() {
    Promise.all([
        api('/status?job=all'),
        api('/api/channels').catch(function () { return { channels: S.channels }; })
    ]).then(function (res) {
        S.online = true;
        S.jobs = (res[0] && res[0].all) || [];
        S.channels = (res[1] && res[1].channels) || {};
        if (!S.selectedJob && !S.selectedDoc) {
            var act = activeJobs();
            S.selectedJob = (act[0] || S.jobs[S.jobs.length - 1] || {}).id || '';
        }
        if (!isEditing()) render();
        else updateChrome();
    }).catch(function () {
        S.online = false;
        updateChrome();
        if (S.route === 'overview' || S.route === 'queue') renderMain();
    });
}
function updateChrome() {
    var act = activeJobs().length;
    if ($('queuebadge')) $('queuebadge').textContent = act;
    if ($('navqueue')) $('navqueue').textContent = act;
    if ($('svcDot')) $('svcDot').className = 'dot ' + (S.online ? 'ok' : 'err');
    if ($('svcText')) $('svcText').textContent = S.online ? '服务在线' : '连接中断';
    if ($('footClock')) $('footClock').textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    if ($('statusQueue')) $('statusQueue').textContent = '队列 ' + act;
    if ($('statusChannels')) {
        var ready = ['mineru', 'dots', 'paddle'].filter(function (k) {
            return S.channels[k] && S.channels[k].configured;
        }).length;
        $('statusChannels').textContent = '渠道 ' + ready + '/3 已配置';
    }
    if ($('statusTime')) $('statusTime').textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    var reviewN = S.reviewCounts.needs_manual_review;
    if (reviewN == null) reviewN = (S.library || []).filter(function (d) {
        return (d.flags || []).indexOf('needs_manual_review') >= 0;
    }).length;
    if ($('navreview')) $('navreview').textContent = reviewN || 0;
    if ($('statusIndex') && S.indexStatus) {
        $('statusIndex').textContent = '索引 ' + (S.indexStatus.with_index || 0) + '/' + (S.indexStatus.out_docs || 0);
    }
    if ($('channelstatus')) {
        $('channelstatus').innerHTML = ['mineru', 'dots', 'paddle'].map(function (k) {
            var c = S.channels[k] || {};
            var cls = !c.configured ? 'off' : (c.state === '有错误' ? 'err' : (c.active ? 'run' : 'ok'));
            return '<span class="ch-dot ' + cls + '" title="' + esc((c.label || k) + '：' + (c.state || '未知')) + '">' +
                k.charAt(0).toUpperCase() + '</span>';
        }).join('');
    }
}

/* ---------------- 渲染入口 ---------------- */
function render() {
    updateChrome();
    var nav = document.querySelectorAll('.nav-item');
    Array.prototype.forEach.call(nav, function (b) {
        b.classList.toggle('cur', b.dataset.route === S.route);
    });
    renderMain();
    renderInspector();
}
function renderMain() {
    var main = $('main');
    if (!main) return;
    if (S.route === 'overview') main.innerHTML = viewOverview();
    else if (S.route === 'queue') { main.innerHTML = viewQueue(); renderQueueRows(); }
    else if (S.route === 'channels') main.innerHTML = viewChannels();
    else if (S.route === 'settings') main.innerHTML = viewSettings();
    else if (S.route === 'library') main.innerHTML = viewLibrary();
    else if (S.route === 'review') main.innerHTML = viewReview();
    else if (S.route === 'reports') main.innerHTML = viewReports();
    else if (S.route === 'eval') main.innerHTML = viewEval();
    else main.innerHTML = '<div class="empty-panel">未知页面</div>';
}

/* ---------------- 总览 ---------------- */
function viewOverview() {
    var scope = (S.library && S.library.length) ? S.library : S.jobs;
    var complete = scope.filter(function (j) { return !(j.missing_channels || []).length; });
    var reviewN = S.reviewCounts.needs_manual_review;
    if (reviewN == null) {
        reviewN = scope.filter(function (j) {
            return ((j.quality || {}).flags || j.flags || []).indexOf('needs_manual_review') >= 0;
        }).length;
    }
    var rate = scope.length ? Math.round(complete.length * 100 / scope.length) : 0;
    var kpis = [
        ['文献总数', scope.length, ''], ['运行/排队', activeJobs().length, 'run'],
        ['三渠道完整', complete.length + '/' + scope.length, rate >= 80 ? 'ok' : 'warn'],
        ['部分异常', S.jobs.filter(function (j) { return j.state === 'degraded'; }).length, 'warn'],
        ['待复核', reviewN, reviewN ? 'warn' : ''],
        ['失败', S.jobs.filter(function (j) { return j.state === 'error'; }).length, 'err']
    ];
    var cards = kpis.map(function (x) {
        return '<div class="metric ' + x[2] + '"><span>' + x[0] + '</span><b>' + x[1] + '</b></div>';
    }).join('');
    return '<div class="pagehead"><div><h1>总览</h1><p>先看任务与渠道，再进入队列处理异常。</p></div>' +
        '<button class="primary" data-action="newbatch">＋ 新建批次</button></div>' +
        '<div class="dropzone" id="drop"><div class="pdf-icon">PDF</div><div><b>拖入 PDF 开始解析</b>' +
        '<span>支持多选；也可以点击选择文件，或复制到 uploads 文件夹</span></div><span class="link">选择 PDF →</span></div>' +
        '<div class="kpis">' + cards + '</div>' +
        '<div class="cols2"><section class="panel"><div class="panel-head"><h2>队列快照</h2>' +
        '<button class="linkbtn" data-route="queue">查看全部 →</button></div>' + queueTable(S.jobs.slice(0, 8), true) +
        '</section><section class="panel"><div class="panel-head"><h2>渠道状态</h2>' +
        '<button class="linkbtn" data-route="channels">配置 →</button></div>' + channelCards() + '</section></div>' +
        '<section class="panel"><div class="panel-head"><h2>最近活动</h2><span class="muted">按更新时间</span></div>' +
        activityList() + '</section>';
}
function activityList() {
    var list = S.jobs.slice().sort(function (a, b) { return (b.updated_at || 0) - (a.updated_at || 0); }).slice(0, 8);
    if (!list.length) return '<div class="empty">暂无任务</div>';
    return '<div class="activity">' + list.map(function (j) {
        var st = stateInfo(j.state);
        return '<button class="activity-row" data-job="' + esc(j.id) + '"><span class="st ' + st[0] + '">' + st[1] +
            '</span><span class="activity-doc">' + esc(j.doc || '(未命名)') + '</span><span class="muted">' +
            esc(j.stage || '') + ' · ' + clock(j.updated_at) + '</span></button>';
    }).join('') + '</div>';
}

/* ---------------- 任务队列 ---------------- */
function viewQueue() {
    var filters = [['all', '全部'], ['active', '运行/排队'], ['stalled', '停滞'],
        ['missing', '缺渠道'], ['degraded', '部分异常'], ['error', '失败'], ['done', '已完成']];
    return '<div class="pagehead"><div><h1>任务队列</h1><p>只展示本服务启动的任务；点击行查看上下文和日志。</p></div>' +
        '<div class="head-actions"><button class="ghost" data-action="refresh">刷新</button>' +
        '<button class="primary" data-action="newbatch">＋ 新建批次</button></div></div>' +
        '<div class="toolbar"><div class="filters">' + filters.map(function (f) {
            return '<button class="chip ' + (S.filter === f[0] ? 'cur' : '') + '" data-filter="' + f[0] + '">' + f[1] + '</button>';
        }).join('') + '</div><input id="queueq" class="search" placeholder="筛选文档名 / 状态" value="' + esc(S.q) + '"></div>' +
        '<section class="panel"><div class="table-wrap"><table class="jobs-table"><thead><tr>' +
        '<th>文档</th><th>状态</th><th>阶段</th><th>三渠道</th><th>心跳</th><th>耗时</th><th>操作</th>' +
        '</tr></thead><tbody id="qbody"></tbody></table></div></section>';
}
function queueRows() {
    var list = S.jobs.slice().sort(function (a, b) {
        var aa = (a.state === '运行中' || a.state === '排队中') ? 1 : 0;
        var bb = (b.state === '运行中' || b.state === '排队中') ? 1 : 0;
        if (aa !== bb) return bb - aa;
        return (b.updated_at || 0) - (a.updated_at || 0);
    });
    var q = (S.q || '').toLowerCase();
    return list.filter(function (j) {
        if (S.filter === 'active') return j.state === '运行中' || j.state === '排队中';
        if (S.filter === 'stalled') return j.stalled;
        if (S.filter === 'missing') return (j.missing_channels || []).length > 0 && (j.state === 'done' || j.state === 'degraded');
        if (S.filter === 'degraded') return j.state === 'degraded';
        if (S.filter === 'error') return j.state === 'error';
        if (S.filter === 'done') return j.state === 'done';
        return true;
    }).filter(function (j) {
        return !q || (j.doc || '').toLowerCase().indexOf(q) >= 0 || (j.stage || '').toLowerCase().indexOf(q) >= 0;
    });
}
function channelPills(j) {
    return ['mineru', 'dots', 'paddle'].map(function (k) {
        var s = (j.channels || {})[k] || 'waiting';
        var present = (j.channel_presence || {})[k];
        var st = STATUS[s] || STATUS.waiting;
        var cls = present ? st[1] : (s === 'running' ? 'run' : (s === 'error' ? 'err' : 'skip'));
        return '<span class="ch-pill ' + cls + '" title="' + CHANNEL_LABELS[k] + '：' + st[0] + '">' +
            k.charAt(0).toUpperCase() + '</span>';
    }).join('');
}
function queueTable(list, compact) {
    if (!list.length) return '<div class="empty">暂无任务</div>';
    return '<div class="table-wrap"><table class="jobs-table"><thead><tr><th>文档</th><th>状态</th><th>阶段</th>' +
        '<th>三渠道</th><th>心跳</th></tr></thead><tbody>' + list.map(function (j) {
            var st = stateInfo(j.state);
            return '<tr class="job-row ' + (j.id === S.selectedJob ? 'cur' : '') + '" data-job="' + esc(j.id) + '">' +
                '<td class="doc-cell"><b>' + esc(j.doc || '(未命名)') + '</b>' +
                (j.stalled ? '<span class="tag warn">停滞</span>' : '') + '</td>' +
                '<td><span class="st ' + st[0] + '">' + st[1] + '</span></td>' +
                '<td class="muted">' + esc(j.stage || '等待调度') + '</td>' +
                '<td class="ch-cell">' + channelPills(j) + '</td>' +
                '<td class="muted">' + (j.heartbeat_age == null ? '-' : j.heartbeat_age + 's') + '</td>' +
                (compact ? '' : '<td class="actions">' + rowActions(j) + '</td>') + '</tr>';
        }).join('') + '</tbody></table></div>';
}
function rowActions(j) {
    var out = '<button class="linkbtn" data-action="diag" data-doc="' + esc(j.doc || '') + '">诊断</button>';
    if ((j.missing_channels || []).length && (j.state === 'done' || j.state === 'degraded')) {
        out += '<button class="linkbtn" data-action="retry-missing" data-doc="' + esc(j.doc || '') + '">补缺渠道</button>';
    }
    if (j.state === 'done' || j.state === 'degraded') {
        out += '<a class="linkbtn" target="_blank" href="/out/' + encodeURIComponent(j.doc || '') + '/index.html">结果</a>';
    }
    return out;
}
function renderQueueRows() {
    var body = $('qbody');
    if (!body) return;
    var rows = queueRows();
    if (!rows.length) {
        body.innerHTML = '<tr><td colspan="7"><div class="empty">没有符合条件的任务</div></td></tr>';
        return;
    }
    body.innerHTML = rows.map(function (j) {
        var st = stateInfo(j.state);
        var missingTag = (j.alerts || []).some(function (a) { return a.kind === 'missing_channel'; })
            ? '<span class="tag warn">缺渠道</span>' : '';
        return '<tr class="job-row ' + (j.id === S.selectedJob ? 'cur' : '') + '" data-job="' + esc(j.id) + '">' +
            '<td class="doc-cell"><b>' + esc(j.doc || '(未命名)') + '</b>' +
            (j.stalled ? '<span class="tag warn">停滞</span>' : '') + missingTag +
            '</td><td><span class="st ' + st[0] + '">' + st[1] + '</span></td>' +
            '<td class="muted">' + esc(j.stage || '等待调度') + '</td><td class="ch-cell">' + channelPills(j) + '</td>' +
            '<td class="muted">' + (j.heartbeat_age == null ? '-' : j.heartbeat_age + 's') + '</td>' +
            '<td class="muted">' + duration(j.elapsed) + (j.state === '排队中' ? ' <span class="tag">排队 ' + duration(j.queue_wait) + '</span>' : '') + '</td>' +
            '<td class="actions">' + rowActions(j) + '</td></tr>';
    }).join('');
}

/* ---------------- 渠道 ---------------- */
function channelCards() {
    return '<div class="channel-cards">' + ['mineru', 'dots', 'paddle'].map(function (k) {
        var c = S.channels[k] || {};
        var cls = !c.configured ? 'off' : (c.state === '有错误' ? 'err' : (c.active ? 'run' : 'ok'));
        return '<div class="channel-card"><div class="ch-head"><b>' + CHANNEL_LABELS[k] + '</b>' +
            '<span class="dot ' + cls + '"></span></div><div class="ch-state">' + esc(c.state || '未知') + '</div>' +
            '<div class="muted">排队/运行 ' + (c.active || 0) + ' · 错误 ' + (c.errors || 0) + '</div>' +
            (c.last_error ? '<div class="err-text">' + esc(c.last_error) + '</div>' : '') + '</div>';
    }).join('') + '</div>';
}
function viewChannels() {
    return '<div class="pagehead"><div><h1>渠道与配额</h1><p>三渠道独立获取；失败只影响该路，可用“补缺渠道”重跑。</p></div>' +
        '<button class="primary" data-action="open-cfg">渠道 API 配置</button></div>' +
        '<section class="panel">' + channelCards() + '<div class="note">Paddle 的 429 才表示账号配额/频率超限；' +
        'pending 长时间不开始属于服务端排队。当前页面不伪造剩余配额，实际额度以账号控制台为准。</div></section>' +
        '<section class="panel"><div class="panel-head"><h2>当前任务中的渠道状态</h2><span class="muted">最多 30 条</span></div>' +
        queueTable(S.jobs.slice(-30), true) + '</section>';
}

/* ---------------- 设置 ---------------- */
function viewSettings() {
    return '<div class="pagehead"><div><h1>设置 / 诊断</h1><p>配置只写入 channels.local.json，不改生成物。</p></div></div>' +
        '<div class="cols2"><section class="panel"><div class="panel-head"><h2>运行状态</h2></div><div class="pad">' +
        '<p>服务：<b>' + (S.online ? '在线' : '离线') + '</b> · 端口 8765</p>' +
        '<p>队列：' + activeJobs().length + ' 个运行/排队 · 共 ' + S.jobs.length + ' 个本服务任务</p>' +
        '<p>结果目录：<code>out/&lt;文档名&gt;/</code>；上传目录：<code>uploads/</code></p>' +
        '<p>数据质量标记来自 <code>metadata.json</code> 的 <code>quality.flags</code>。</p></div></section>' +
        '<section class="panel"><div class="panel-head"><h2>操作</h2></div><div class="pad actions-col">' +
        '<button class="primary" data-action="open-cfg">打开渠道配置</button>' +
        '<button class="ghost" data-action="newbatch">新建批次</button>' +
        '<button class="ghost" data-action="copy-diag">复制当前诊断</button></div></section></div>' +
        '<section class="panel"><div class="panel-head"><h2>回退点</h2></div><div class="pad">' +
        '<p>改造前基线：<code>d712eba</code>，标签 <code>pre-ui-workbench-20261118</code>。</p>' +
        '<p>完整 bundle / 静态快照 / 回退说明位于仓库外 <code>D:\\处理工具\\2\\_backups\\ui-workbench-20261118</code>。</p>' +
        '<p class="muted">回退只覆盖 webapp.py、app.js、dashboard.css 和新增测试，不删除 out/ 与 uploads/。</p></div></section>';
}

/* ---------------- 文献库 / 复核 / 报告 / 评测 ---------------- */
function libItems() {
    var q = (S.libQ || '').toLowerCase();
    var f = S.libFilter || '';
    return (S.library || []).filter(function (d) {
        if (f && (d.flags || []).indexOf(f) < 0) return false;
        if (!q) return true;
        return (d.doc + ' ' + (d.title || '') + ' ' + (d.author_text || '') + ' ' + (d.journal || '')).toLowerCase().indexOf(q) >= 0;
    });
}
function viewLibrary() {
    var items = libItems();
    var flags = [['', '全部'], ['needs_manual_review', '需复核'], ['title_missing', '题名缺失'],
        ['authors_missing', '作者缺失'], ['journal_missing', '期刊缺失'], ['year_missing', '年份缺失']];
    return '<div class="pagehead"><div><h1>文献库</h1><p>共 ' + (S.library || []).length +
        ' 篇有产物文献；点击行查看元数据与渠道。</p></div><div class="head-actions">' +
        '<a class="ghost btnlink" href="/api/export?fmt=csv">导出 CSV</a>' +
        '<a class="ghost btnlink" href="/api/export?fmt=bib">导出 BibTeX</a></div></div>' +
        '<div class="toolbar"><div class="filters">' + flags.map(function (x) {
            return '<button class="chip ' + (S.libFilter === x[0] ? 'cur' : '') + '" data-libfilter="' + x[0] + '">' + x[1] + '</button>';
        }).join('') + '</div><input id="libq" class="search" placeholder="搜索题名 / 作者 / 文档名" value="' + esc(S.libQ || '') + '"></div>' +
        '<section class="panel"><div class="table-wrap"><table class="jobs-table"><thead><tr>' +
        '<th>题名 / 文档</th><th>作者</th><th>期刊 / 年份</th><th>质量标记</th><th>渠道</th><th>复核</th></tr></thead><tbody id="libbody">' +
        (items.length ? items.map(function (d) {
            return '<tr class="job-row" data-doc="' + esc(d.doc) + '"><td class="doc-cell"><b>' +
                esc(d.title || d.doc) + '</b><div class="muted small">' + esc(d.doc) + '</div></td>' +
                '<td>' + esc(d.author_text || '—') + '</td><td>' + esc(d.journal || '—') +
                ' <span class="muted">' + esc(d.year || '') + '</span></td><td class="flag-cell">' + flagTags(d.flags, 3) + '</td>' +
                '<td class="ch-cell">' + docChannelPills(d) + '</td><td>' + (d.reviewed ? '<span class="st ok">已覆盖</span>' : '<span class="muted">—</span>') + '</td></tr>';
        }).join('') : '<tr><td colspan="6"><div class="empty">没有匹配文献</div></td></tr>') +
        '</tbody></table></div></section>';
}
function docChannelPills(d) {
    return ['mineru', 'dots', 'paddle'].map(function (k) {
        var yes = (d.channels || {})[k];
        return '<span class="ch-pill ' + (yes ? 'ok' : 'skip') + '" title="' + CHANNEL_LABELS[k] + '">' +
            k.charAt(0).toUpperCase() + '</span>';
    }).join('');
}
function reviewFiltered() {
    var f = S.reviewFilter || '';
    return (S.review || []).filter(function (d) { return !f || (d.flags || []).indexOf(f) >= 0; });
}
function viewReview() {
    var list = reviewFiltered();
    var counts = S.reviewCounts || {};
    var chips = [['', '全部'], ['needs_manual_review', '需人工复核'], ['title_missing', '题名'],
        ['authors_missing', '作者'], ['journal_missing', '期刊'], ['year_missing', '年份'],
        ['references_incomplete', '参考文献'], ['citations_unresolved', '引文']];
    return '<div class="pagehead"><div><h1>质量复核</h1><p>按异常处理，不逐篇盲翻；人工值写入 <code>metadata_override.json</code>。</p></div>' +
        '<div class="head-actions"><span class="muted">待复核 ' + (counts.needs_manual_review || 0) + ' 篇</span></div></div>' +
        '<div class="toolbar"><div class="filters">' + chips.map(function (x) {
            return '<button class="chip ' + (S.reviewFilter === x[0] ? 'cur' : '') + '" data-reviewfilter="' + x[0] + '">' +
                x[1] + (x[0] && counts[x[0]] ? ' ' + counts[x[0]] : '') + '</button>';
        }).join('') + '</div></div>' +
        '<div class="review-layout"><section class="panel review-list"><div class="panel-head"><h2>问题清单</h2><span class="muted">' +
        list.length + ' 篇</span></div><div class="review-items">' + (list.length ? list.map(function (d) {
            return '<button class="review-item ' + (S.reviewDoc && S.reviewDoc.doc === d.doc ? 'cur' : '') +
                '" data-reviewdoc="' + esc(d.doc) + '"><b>' + esc(d.title || d.doc) + '</b><span>' +
                esc(d.author_text || '作者未知') + ' · ' + esc(d.year || '年份未知') + '</span><div>' +
                flagTags(d.flags, 2) + '</div></button>';
        }).join('') : '<div class="empty">没有匹配的问题</div>') + '</div></section>' +
        '<section class="panel review-editor" id="reviewEditor">' + reviewEditor() + '</section></div>';
}
function reviewEditor() {
    var d = S.reviewDoc;
    if (!d) return '<div class="empty-panel">从左侧选择一篇文献开始复核。</div>';
    var f = d.fields || {};
    var authors = Array.isArray(f.authors) ? f.authors.join('\n') : (f.authors || '');
    var fields = [
        ['title', '题名', f.title || '', 'text'],
        ['authors', '作者（每行一位）', authors, 'textarea'],
        ['journal', '期刊', f.journal || '', 'text'],
        ['year', '年份', f.year || '', 'text'],
        ['volume', '卷', f.volume || '', 'text'],
        ['issue', '期', f.issue || '', 'text'],
        ['pages', '页码', f.pages || '', 'text'],
        ['document_type', '类型', f.document_type || '', 'text']
    ];
    var inputs = fields.map(function (x) {
        var id = 'rf_' + x[0];
        return '<label for="' + id + '">' + x[1] + '</label>' + (x[3] === 'textarea'
            ? '<textarea id="' + id + '" rows="3">' + esc(x[2]) + '</textarea>'
            : '<input id="' + id + '" value="' + esc(x[2]) + '">');
    }).join('');
    var audit = (d.audit || []).slice(-4).reverse().map(function (a) {
        return '<div class="audit-row"><b>' + esc(a.updated || '') + '</b><span>' + esc(a.note || '人工修改') + '</span></div>';
    }).join('') || '<div class="muted small">尚无人工修改记录</div>';
    return '<div class="panel-head"><h2>' + esc(d.doc) + '</h2><span class="muted">' + esc((d.flags || []).join(' / ')) + '</span></div>' +
        '<div class="pad"><div class="review-flags">' + flagTags(d.flags, 8) + '</div><div class="form-grid">' + inputs + '</div>' +
        '<label for="rf_note">修改备注</label><input id="rf_note" placeholder="例如：题名按首页栏题补全">' +
        '<div class="review-foot"><button class="primary" data-action="save-override">保存人工覆盖</button>' +
        '<button class="ghost" data-action="review-next">保存并下一篇</button>' +
        '<a class="ghost btnlink" target="_blank" href="/out/' + encodeURIComponent(d.doc) + '/index.html">打开结果</a></div>' +
        '<h3>修改记录</h3>' + audit + '</div>';
}
function viewReports() {
    var items = S.library || [];
    if (!items.length) return '<div class="pagehead"><div><h1>批次报告</h1></div></div><div class="empty-panel">正在加载文献库…</div>';
    var complete = items.filter(function (d) { return !(d.missing_channels || []).length; });
    var withIndex = items.filter(function (d) { return d.has_index; });
    var reviewed = items.filter(function (d) { return d.reviewed; });
    var flagCount = {};
    items.forEach(function (d) { (d.flags || []).forEach(function (f) { flagCount[f] = (flagCount[f] || 0) + 1; }); });
    var top = Object.keys(flagCount).sort(function (a, b) { return flagCount[b] - flagCount[a]; }).slice(0, 10);
    return '<div class="pagehead"><div><h1>批次报告</h1><p>当前文献库汇总；导出使用同一份 effective 字段（含人工覆盖）。</p></div>' +
        '<div class="head-actions"><a class="ghost btnlink" href="/api/export?fmt=csv">CSV</a>' +
        '<a class="ghost btnlink" href="/api/export?fmt=bib">BibTeX</a>' +
        '<a class="ghost btnlink" href="/api/export?fmt=json">JSON</a></div></div>' +
        '<div class="kpis report-kpis">' +
        '<div class="metric"><span>文献总数</span><b>' + items.length + '</b></div>' +
        '<div class="metric ok"><span>三渠道齐全</span><b>' + complete.length + '</b></div>' +
        '<div class="metric run"><span>有结果页</span><b>' + withIndex.length + '</b></div>' +
        '<div class="metric warn"><span>已人工覆盖</span><b>' + reviewed.length + '</b></div></div>' +
        '<div class="cols2"><section class="panel"><div class="panel-head"><h2>质量问题分布</h2></div><div class="pad">' +
        (top.length ? top.map(function (f) {
            return '<div class="bar-row"><span>' + esc(flagLabel(f)) + '</span><div class="bar"><i style="width:' +
                Math.min(100, flagCount[f] * 100 / Math.max(1, items.length)) + '%"></i></div><b>' + flagCount[f] + '</b></div>';
        }).join('') : '<div class="muted">暂无质量标记</div>') + '</div></section>' +
        '<section class="panel"><div class="panel-head"><h2>完整率</h2></div><div class="pad"><p>三渠道齐全：<b>' +
        Math.round(complete.length * 100 / Math.max(1, items.length)) + '%</b></p><p>结果页：<b>' +
        Math.round(withIndex.length * 100 / Math.max(1, items.length)) + '%</b></p><p class="muted">缺失渠道可在文献详情或任务队列补跑。</p></div></section></div>';
}
function viewEval() {
    var reports = S.evalReports || [];
    var cur = reports.filter(function (r) { return r.name === S.evalSel; })[0] || reports[0];
    var idx = S.indexStatus || {};
    var summary = (cur && cur.summary) || {};
    var order = ['docs', 'title_exact', 'title_acceptable', 'title_avg_ratio', 'author_docs_ok',
        'author_docs_expected', 'author_f1_avg', 'refs_f1_avg', 'applicable_core_ok', 'strict_core_ok',
        'field_coverage', 'field_coverage_max'];
    return '<div class="pagehead"><div><h1>评测</h1><p>只读展示 eval/reports 下的金标准结果；不会在页面里自动跑长时间评测。</p></div></div>' +
        '<div class="kpis report-kpis"><div class="metric"><span>输出文献</span><b>' + (idx.out_docs || 0) + '</b></div>' +
        '<div class="metric run"><span>有结果页</span><b>' + (idx.with_index || 0) + '</b></div>' +
        '<div class="metric"><span>有元数据</span><b>' + (idx.with_metadata || 0) + '</b></div>' +
        '<div class="metric ok"><span>归档条目</span><b>' + (idx.archive_items || 0) + '</b></div></div>' +
        '<div class="cols2"><section class="panel"><div class="panel-head"><h2>评测报告</h2><span class="muted">' + reports.length + ' 份</span></div>' +
        '<div class="review-items">' + (reports.length ? reports.map(function (r) {
            return '<button class="review-item ' + (cur && cur.name === r.name ? 'cur' : '') + '" data-eval="' + esc(r.name) +
                '"><b>' + esc(r.name) + '</b><span>' + r.rows + ' 行 · ' + clock(r.updated) + '</span></button>';
        }).join('') : '<div class="empty">没有评测报告</div>') + '</div></section>' +
        '<section class="panel"><div class="panel-head"><h2>' + esc(cur ? cur.name : '指标') + '</h2></div><div class="pad">' +
        (cur ? '<table class="kv-table">' + order.filter(function (k) { return summary[k] !== undefined; }).map(function (k) {
            return '<tr><th>' + esc(k) + '</th><td>' + esc(summary[k]) + '</td></tr>';
        }).join('') + '</table>' : '<div class="muted">选择一份报告</div>') + '</div></section></div>' +
        '<section class="panel"><div class="panel-head"><h2>索引状态</h2></div><div class="pad">' +
        '<p>输出目录：' + (idx.out_docs || 0) + ' 篇 · 结果页：' + (idx.with_index || 0) +
        ' · 元数据：' + (idx.with_metadata || 0) + '</p><p>归档索引：' +
        (idx.archive_exists ? '存在，' + (idx.archive_items || 0) + ' 条' : '尚未创建') + '</p></div></section>';
}

/* ---------------- 右侧检查器 ---------------- */
function renderInspector() {
    var el = $('inspector');
    if (!el) return;
    var j = selectedJob();
    if (!j && S.selectedDoc) {
        renderDocInspector(el);
        return;
    }
    if (!j) {
        el.innerHTML = '<div class="empty-panel">选择任务或文献后，这里显示上下文、日志和操作。</div>';
        return;
    }
    var st = stateInfo(j.state);
    var stages = PIPELINE.map(function (s, i) {
        var ss = (j.stages || {})[s[0]] || 'waiting';
        var info = STATUS[ss] || STATUS.waiting;
        return '<div class="mini-step ' + info[1] + '"><span>' + (i + 1) + '</span><b>' + s[1] + '</b><em>' + info[0] + '</em></div>';
    }).join('');
    var alerts = (j.alerts || []).map(function (a) {
        return '<div class="alert ' + a.level + '">' + esc(a.text) + '</div>';
    }).join('') || '<div class="okline">暂无阻塞告警</div>';
    var diag = (S.diag && S.diag.doc === j.doc) ? S.diag : null;
    var logs = diag && diag.job && diag.job.log ? diag.job.log.slice(-12) : [j.logline].filter(Boolean);
    el.innerHTML = '<div class="inspector-head"><div><span class="eyebrow">任务上下文</span><h2>' + esc(j.doc || '(未命名)') + '</h2>' +
        '<div class="muted">' + esc(j.id) + '</div></div><button class="iconbtn" data-action="close-inspector" title="关闭">×</button></div>' +
        '<div class="inspector-body"><div class="inspector-status"><span class="st ' + st[0] + '">' + st[1] + '</span>' +
        '<span class="muted">' + esc(j.stage || '等待调度') + '</span></div>' +
        '<div class="kv"><span>心跳</span><b>' + (j.heartbeat_age == null ? '-' : j.heartbeat_age + ' 秒前') + '</b>' +
        '<span>耗时</span><b>' + duration(j.elapsed) + '</b><span>排队</span><b>' + duration(j.queue_wait) + '</b>' +
        '<span>补跑</span><b>' + esc(j.rescue || '—') + '</b></div>' +
        '<h3>三渠道矩阵</h3><div class="matrix">' + ['mineru', 'dots', 'paddle'].map(function (k) {
            var ss = (j.channels || {})[k] || 'waiting';
            var info = STATUS[ss] || STATUS.waiting;
            var present = (j.channel_presence || {})[k];
            return '<div class="matrix-row"><b>' + CHANNEL_LABELS[k] + '</b><span class="st ' + info[1] + '">' + info[0] + '</span>' +
                '<span class="muted">' + (present ? '产物已落地' : '无产物') + '</span></div>';
        }).join('') + '</div>' +
        '<h3>阶段时间线</h3><div class="mini-steps">' + stages + '</div>' +
        '<h3>诊断</h3>' + alerts +
        '<h3>最近日志</h3><pre class="logbox" id="logbox">' + (logs.length ? esc(logs.join('\n')) : '暂无日志') + '</pre></div>' +
        '<div class="inspector-actions">' +
        ((j.missing_channels || []).length ? '<button class="primary" data-action="retry-missing" data-doc="' + esc(j.doc || '') + '">补缺渠道</button>' : '') +
        '<button class="ghost" data-action="copy-diag" data-doc="' + esc(j.doc || '') + '">复制诊断</button>' +
        ((j.state === 'done' || j.state === 'degraded') ? '<a class="ghost btnlink" target="_blank" href="/out/' + encodeURIComponent(j.doc || '') + '/index.html">打开结果</a>' : '') +
        '</div>';
    var lb = $('logbox');
    if (lb) lb.scrollTop = lb.scrollHeight;
}
function renderDocInspector(el) {
    var d = S.doc;
    if (!d) {
        el.innerHTML = '<div class="empty-panel">正在读取文献元数据…</div>';
        return;
    }
    var rec = d.record || {};
    var f = d.fields || {};
    var audit = (d.audit || []).slice(-3).reverse().map(function (a) {
        return '<div class="audit-row"><b>' + esc(a.updated || '') + '</b><span>' + esc(a.note || '人工修改') + '</span></div>';
    }).join('');
    el.innerHTML = '<div class="inspector-head"><div><span class="eyebrow">文献上下文</span><h2>' +
        esc(f.title || rec.doc || '(无题名)') + '</h2><div class="muted">' + esc(d.doc) + '</div></div>' +
        '<button class="iconbtn" data-action="close-inspector" title="关闭">×</button></div>' +
        '<div class="inspector-body"><div class="matrix">' + ['mineru', 'dots', 'paddle'].map(function (k) {
            var yes = (d.channels || {})[k];
            return '<div class="matrix-row"><b>' + CHANNEL_LABELS[k] + '</b><span class="st ' +
                (yes ? 'ok' : 'warn') + '">' + (yes ? '有产物' : '缺失') + '</span><span class="muted">' +
                (yes ? 'raw 已落地' : '可补跑') + '</span></div>';
        }).join('') + '</div>' +
        '<h3>effective 字段</h3><div class="doc-fields">' +
        [['作者', (f.authors || []).join('、')], ['期刊', f.journal], ['年份', f.year],
         ['卷 / 期', [f.volume, f.issue].filter(Boolean).join(' / ')], ['页码', f.pages],
         ['类型', f.document_type]].map(function (x) {
            return '<div><span>' + x[0] + '</span><b>' + esc(x[1] || '—') + '</b></div>';
        }).join('') + '</div>' +
        '<h3>质量标记</h3><div>' + (flagTags(d.flags, 12) || '<span class="okline">无标记</span>') + '</div>' +
        (audit ? '<h3>最近人工修改</h3>' + audit : '') + '</div>' +
        '<div class="inspector-actions"><button class="primary" data-action="review-doc" data-doc="' + esc(d.doc) + '">去复核</button>' +
        ((d.missing_channels || []).length ? '<button class="ghost" data-action="retry-missing" data-doc="' + esc(d.doc) + '">补缺渠道</button>' : '') +
        '<a class="ghost btnlink" target="_blank" href="/out/' + encodeURIComponent(d.doc) + '/index.html">打开结果</a></div>';
}
function loadDiag(doc) {
    if (!doc) return;
    api('/api/diag?doc=' + encodeURIComponent(doc)).then(function (data) {
        S.diag = data;
        if (S.selectedJob && selectedJob() && selectedJob().doc === doc) renderInspector();
    }).catch(function () { });
}
function selectJob(id) {
    S.selectedJob = id;
    S.selectedDoc = '';
    var j = selectedJob();
    if (j) loadDiag(j.doc);
    if (S.route === 'queue') renderQueueRows();
    renderInspector();
}

/* ---------------- 操作 ---------------- */
function go(file) {
    if (!/\.pdf$/i.test(file.name)) return Promise.resolve();
    toast('正在上传 ' + file.name);
    return api('/upload?name=' + encodeURIComponent(file.name), { method: 'POST', body: file })
        .then(function (b) {
            if (b && b.dup) { toast(b.msg || '该文献已归档，已跳过', true); return; }
            toast('已进入解析队列');
        }).catch(function (e) { toast('上传失败：' + e.message, true); });
}
function uploadFiles(files) {
    var list = Array.prototype.slice.call(files || []);
    if (!list.length) return;
    var chain = Promise.resolve();
    list.forEach(function (f) { chain = chain.then(function () { return go(f); }); });
    chain.then(function () { $('f').value = ''; tick(); });
}
function retryMissing(doc) {
    if (!doc) return;
    api('/api/retry-missing?doc=' + encodeURIComponent(doc), { method: 'POST' })
        .then(function (b) { toast('已加入补跑队列：' + (b.missing || []).join(' / ')); tick(); })
        .catch(function (e) { toast('补跑失败：' + e.message, true); });
}
function copyDiag(doc) {
    var j = selectedJob();
    var text = '';
    if (S.diag && S.diag.doc === doc) {
        text = JSON.stringify(S.diag, null, 2);
    } else if (j) {
        text = JSON.stringify({ id: j.id, doc: j.doc, state: j.state, stage: j.stage, channels: j.channels, alerts: j.alerts, logline: j.logline }, null, 2);
    }
    if (!text) { toast('没有可复制的诊断信息', true); return; }
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () { toast('诊断信息已复制'); });
    } else {
        var ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); toast('诊断信息已复制'); } catch (e) { toast('复制失败', true); }
        document.body.removeChild(ta);
    }
}

/* ---------------- 数据加载与 P1 操作 ---------------- */
function loadLibrary() {
    S.libLoading = true;
    return api('/api/library').then(function (data) {
        S.library = (data && data.items) || [];
        S.libLoading = false;
        if (S.route === 'library' || S.route === 'reports') renderMain();
    }).catch(function (e) {
        S.libLoading = false;
        toast('文献库加载失败：' + e.message, true);
    });
}
function loadReview() {
    return api('/api/review').then(function (data) {
        S.review = (data && data.items) || [];
        S.reviewCounts = (data && data.counts) || {};
        if (S.route === 'review') {
            if (!S.reviewDoc) {
                var first = reviewFiltered()[0];
                if (first) { loadReviewDoc(first.doc); return; }
            }
            renderMain();
        }
    }).catch(function (e) { toast('复核清单加载失败：' + e.message, true); });
}
function loadReviewDoc(doc) {
    if (!doc) return;
    api('/api/doc?doc=' + encodeURIComponent(doc)).then(function (data) {
        S.reviewDoc = data;
        S.doc = data;
        S.selectedDoc = doc;
        S.selectedJob = '';
        if (S.route === 'review') renderMain();
        renderInspector();
    }).catch(function (e) { toast('文献读取失败：' + e.message, true); });
}
function loadReports() {
    if (!S.library.length) {
        loadLibrary().then(function () { if (S.route === 'reports') renderMain(); });
    }
}
function loadEval() {
    Promise.all([api('/api/eval'), api('/api/index')]).then(function (res) {
        S.evalReports = (res[0] && res[0].reports) || [];
        S.indexStatus = res[1] || {};
        if (!S.evalSel && S.evalReports.length) S.evalSel = S.evalReports[0].name;
        if (S.route === 'eval') renderMain();
    }).catch(function (e) { toast('评测数据加载失败：' + e.message, true); });
}
function openDocDetail(doc) {
    if (!doc) return;
    S.selectedDoc = doc;
    S.selectedJob = '';
    S.doc = null;
    renderInspector();
    api('/api/doc?doc=' + encodeURIComponent(doc)).then(function (data) {
        S.doc = data;
        renderInspector();
    }).catch(function (e) { toast('文献读取失败：' + e.message, true); });
}
function overrideFields() {
    var out = {};
    ['title', 'authors', 'journal', 'year', 'volume', 'issue', 'pages', 'document_type'].forEach(function (k) {
        var el = $('rf_' + k);
        if (!el) return;
        out[k] = k === 'authors' ? el.value.split(/\n+/) : el.value;
    });
    return out;
}
function saveOverride(next) {
    if (!S.reviewDoc) return;
    var note = ($('rf_note') || {}).value || '';
    api('/api/override', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc: S.reviewDoc.doc, fields: overrideFields(), note: note }) })
        .then(function (res) {
            S.reviewDoc = res.data;
            S.doc = res.data;
            toast('已保存人工覆盖');
            var lib = S.library.filter(function (d) { return d.doc === res.data.doc; })[0];
            if (lib) { lib.reviewed = true; lib.flags = res.data.flags; }
            if (next) reviewNext(); else renderMain();
        }).catch(function (e) { toast('保存失败：' + e.message, true); });
}
function reviewNext() {
    var list = reviewFiltered();
    var i = -1;
    list.forEach(function (d, n) { if (S.reviewDoc && d.doc === S.reviewDoc.doc) i = n; });
    if (i >= 0 && list[i + 1]) loadReviewDoc(list[i + 1].doc);
    else toast('当前筛选下已到最后一篇');
}
function renderLibRows() {
    var body = $('libbody');
    if (!body) return;
    var items = libItems();
    body.innerHTML = items.length ? items.map(function (d) {
        return '<tr class="job-row" data-doc="' + esc(d.doc) + '"><td class="doc-cell"><b>' +
            esc(d.title || d.doc) + '</b><div class="muted small">' + esc(d.doc) + '</div></td>' +
            '<td>' + esc(d.author_text || '—') + '</td><td>' + esc(d.journal || '—') +
            ' <span class="muted">' + esc(d.year || '') + '</span></td><td class="flag-cell">' + flagTags(d.flags, 3) + '</td>' +
            '<td class="ch-cell">' + docChannelPills(d) + '</td><td>' + (d.reviewed ? '<span class="st ok">已覆盖</span>' : '<span class="muted">—</span>') + '</td></tr>';
    }).join('') : '<tr><td colspan="6"><div class="empty">没有匹配文献</div></td></tr>';
}

/* ---------------- 事件 ---------------- */
document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-action],[data-route],[data-filter],[data-libfilter],[data-reviewfilter],[data-reviewdoc],[data-eval],[data-doc],[data-job]') : null;
    if (!t) return;
    if (t.dataset.route) { e.preventDefault(); setRoute(t.dataset.route); return; }
    if (t.dataset.filter) { S.filter = t.dataset.filter; renderMain(); return; }
    if (t.dataset.libfilter !== undefined) { S.libFilter = t.dataset.libfilter; renderMain(); return; }
    if (t.dataset.reviewfilter !== undefined) { S.reviewFilter = t.dataset.reviewfilter; renderMain(); return; }
    if (t.dataset.reviewdoc) { loadReviewDoc(t.dataset.reviewdoc); return; }
    if (t.dataset.eval) { S.evalSel = t.dataset.eval; renderMain(); return; }
    if (t.dataset.action === 'newbatch') { $('f').click(); return; }
    if (t.dataset.action === 'refresh') { tick(); toast('已刷新'); return; }
    if (t.dataset.action === 'open-cfg') { openCfg(); return; }
    if (t.dataset.action === 'copy-diag') { copyDiag(t.dataset.doc); return; }
    if (t.dataset.action === 'retry-missing') { e.stopPropagation(); retryMissing(t.dataset.doc); return; }
    if (t.dataset.action === 'diag') { e.stopPropagation(); S.selectedDoc = ''; selectJob(findJobByDoc(t.dataset.doc)); return; }
    if (t.dataset.action === 'close-inspector') { S.selectedJob = ''; S.selectedDoc = ''; S.doc = null; renderInspector(); return; }
    if (t.dataset.action === 'review-doc') {
        e.stopPropagation();
        S.route = 'review';
        S.reviewDoc = S.doc;
        render();
        loadReview().then(function () { loadReviewDoc(t.dataset.doc); });
        return;
    }
    if (t.dataset.action === 'save-override') { saveOverride(false); return; }
    if (t.dataset.action === 'review-next') { saveOverride(true); return; }
    if (t.dataset.job) { selectJob(t.dataset.job); return; }
    if (t.dataset.doc) { openDocDetail(t.dataset.doc); return; }
});
function findJobByDoc(doc) {
    for (var i = S.jobs.length - 1; i >= 0; i--) if (S.jobs[i].doc === doc) return S.jobs[i].id;
    return '';
}
document.addEventListener('input', function (e) {
    if (e.target.id === 'queueq') { S.q = e.target.value; renderQueueRows(); }
    if (e.target.id === 'libq') { S.libQ = e.target.value; renderLibRows(); }
});
document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if ($('globalq')) $('globalq').focus();
    }
    if (e.key === 'Escape') {
        if ($('cfgpanel')) $('cfgpanel').style.display = 'none';
    }
});
function setRoute(route, keepHash) {
    S.route = route;
    S.selectedDoc = '';
    if (!keepHash && location.hash.slice(1) !== route) {
        try { history.replaceState(null, '', '#' + route); } catch (e) { }
    }
    if (route === 'library' && typeof loadLibrary === 'function') loadLibrary();
    if (route === 'review' && typeof loadReview === 'function') loadReview();
    if (route === 'reports' && typeof loadReports === 'function') loadReports();
    if (route === 'eval' && typeof loadEval === 'function') loadEval();
    render();
}
window.addEventListener('hashchange', function () {
    var r = location.hash.slice(1);
    if (r && r !== S.route) setRoute(r, true);
});

/* ---------------- 上传/拖拽 ---------------- */
$('f').onchange = function () { uploadFiles(this.files); };
document.addEventListener('dragover', function (e) { e.preventDefault(); });
document.addEventListener('drop', function (e) {
    e.preventDefault();
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
});
$('newbatch').onclick = function () { $('f').click(); };
$('topqueue').onclick = function () { setRoute('queue'); };
$('settingsbtn').onclick = function () { setRoute('settings'); };
$('globalq').addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { S.libQ = this.value; S.q = this.value; setRoute('library'); }
});
Array.prototype.forEach.call(document.querySelectorAll('.nav-item'), function (b) {
    b.onclick = function () { setRoute(this.dataset.route); };
});

/* ---------------- 渠道 API 配置 ---------------- */
var SCHEMA = [
    { sec: 'mineru_api', label: 'MinerU 云端 API', fields: [
        { k: 'token', label: 'Token', ph: 'sk-...' },
        { k: 'model_version', label: '模型版本', sel: ['pipeline', 'vlm', 'MinerU-HTML'] },
        { k: 'language', label: '语言（日文=japan）', sel: ['japan', 'ch', 'en', 'korean', 'chinese_cht', 'latin'] },
        { k: 'timeout', label: '超时（秒）', num: 1 }
    ] },
    { sec: 'paddle_api', label: 'PaddleOCR 云端 API', fields: [
        { k: 'token', label: 'Token', ph: 'aistudio token' },
        { k: 'model', label: '模型', ph: 'PaddleOCR-VL-1.6' },
        { k: 'base', label: 'API 地址', ph: 'https://paddleocr.aistudio-app.com' },
        { k: 'timeout', label: '超时（秒）', num: 1 }
    ] },
    { sec: 'dots_api', label: 'dots.ocr 云端 API', fields: [
        { k: 'base', label: '实例地址', ph: 'https://dotsocr.xiaohongshu.com' },
        { k: 'model', label: '模型', sel: ['dots.mocr', 'dots.mocr-svg'] },
        { k: 'prompt', label: 'Prompt 键', ph: 'prompt_layout_all_en' },
        { k: 'timeout', label: '超时（秒）', num: 1 }
    ] }
];
function buildForm(cfg) {
    cfg = cfg || {};
    $('cfgform').innerHTML = SCHEMA.map(function (s) {
        var rows = s.fields.map(function (ft) {
            var v = (cfg[s.sec] || {})[ft.k];
            if (v === undefined || v === null) v = '';
            var id = 'c_' + s.sec + '_' + ft.k, inp;
            if (ft.sel) {
                inp = '<select id="' + id + '">' + ft.sel.map(function (o) {
                    return '<option' + (o == v ? ' selected' : '') + '>' + esc(o) + '</option>';
                }).join('') + '</select>';
            } else {
                inp = '<input type="' + (ft.num ? 'number' : 'text') + '" id="' + id + '" value="' + esc(v) + '" placeholder="' + esc(ft.ph || '') + '">';
            }
            return '<label>' + esc(ft.label) + '</label>' + inp;
        }).join('');
        return '<div class="sec"><b>' + esc(s.label) + '</b>' + rows + '</div>';
    }).join('');
}
function openCfg() {
    $('cfgpanel').style.display = 'block';
    $('cfgmsg').textContent = '';
    api('/api/config').then(buildForm).catch(function () { buildForm({}); });
}
$('closecfg').onclick = function () { $('cfgpanel').style.display = 'none'; };
$('savecfg').onclick = function () {
    var out = {};
    SCHEMA.forEach(function (s) {
        out[s.sec] = {};
        s.fields.forEach(function (ft) {
            var el = $('c_' + s.sec + '_' + ft.k);
            out[s.sec][ft.k] = ft.num ? parseInt(el.value || '0', 10) : el.value;
        });
    });
    api('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(out) })
        .then(function () {
            $('cfgmsg').textContent = '已保存 ' + new Date().toLocaleTimeString('zh-CN', { hour12: false });
            setTimeout(function () { $('cfgpanel').style.display = 'none'; }, 700);
            tick();
        }).catch(function (e) { $('cfgmsg').textContent = '保存失败：' + e.message; });
};

/* 启动 */
var initialRoute = location.hash.slice(1);
var qdoc = '';
try { qdoc = new URLSearchParams(location.search).get('doc') || ''; } catch (e) { }
if (initialRoute) setRoute(initialRoute, true);
if (qdoc && initialRoute === 'review') loadReview().then(function () { loadReviewDoc(qdoc); });
if (qdoc && initialRoute === 'library') openDocDetail(qdoc);
tick();
function afterSummary() {
    updateChrome();
    if (S.route === 'overview') renderMain();
}
loadLibrary().then(afterSummary);
if (initialRoute !== 'review') loadReview().then(afterSummary);
api('/api/index').then(function (idx) { S.indexStatus = idx; updateChrome(); }).catch(function () { });
setInterval(tick, 2000);
