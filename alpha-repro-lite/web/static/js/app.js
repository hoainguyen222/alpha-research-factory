/* ═══════════════════════════════════════════════════════════════════
   ALPHA RESEARCH FACTORY — Dashboard Client Controller
   ═══════════════════════════════════════════════════════════════════ */

// ─── Top Metrics Live Updater ─────────────────────────────────────
async function refreshTopMetrics() {
    try {
        const res = await fetch('/api/vault/stats');
        const data = await res.json();
        if (data.status === 'success' && data.stats) {
            const totalVault = data.stats.total_entries || 0;
            const elVault = document.getElementById('statVault');
            if (elVault) elVault.textContent = totalVault;
            
            const elScraped = document.getElementById('statScraped');
            if (elScraped) elScraped.textContent = Math.max(0, totalVault - 1);
        }
    } catch (e) {
        console.error('Failed to refresh top metrics:', e);
    }
}

// ─── Tab Navigation ─────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
        
        refreshTopMetrics();
        // Tự động tải lại dữ liệu của Tab khi người dùng bấm chuyển Tab
        if (btn.dataset.tab === 'components') loadComponents();
        if (btn.dataset.tab === 'rules') { if (typeof loadRules === 'function') loadRules(); if (typeof loadTemplates === 'function') loadTemplates(); }
        if (btn.dataset.tab === 'vault') { if (typeof searchVault === 'function') searchVault(); }
        if (btn.dataset.tab === 'leaderboard') { if (typeof loadLeaderboard === 'function') loadLeaderboard(); }
    });
});
refreshTopMetrics();

// ─── Leaderboard ────────────────────────────────────────────────
async function loadLeaderboard() {
    try {
        const res = await fetch('/api/leaderboard');
        const data = await res.json();
        const tbody = document.getElementById('leaderboardBody');
        if (!data.strategies || data.strategies.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Chưa có chiến lược nào. Hãy chạy Alpha Factory!</td></tr>';
            return;
        }
        tbody.innerHTML = data.strategies.map((s, i) => `
            <tr>
                <td><strong>#${i + 1}</strong></td>
                <td>${s.paper_id || ''}</td>
                <td>${s.symbol} (${s.timeframe})</td>
                <td class="${s.sharpe_ratio >= 0 ? 'val-positive' : 'val-negative'}">${(s.sharpe_ratio || 0).toFixed(2)}</td>
                <td>${(s.sortino_ratio || 0).toFixed(2)}</td>
                <td>${(s.calmar_ratio || 0).toFixed(2)}</td>
                <td>${(s.profit_factor || 0).toFixed(2)}</td>
                <td>${(s.hit_rate_pct || 0).toFixed(1)}%</td>
                <td class="${s.total_return_pct >= 0 ? 'val-positive' : 'val-negative'}">${s.total_return_pct >= 0 ? '+' : ''}${(s.total_return_pct || 0).toFixed(1)}%</td>
                <td class="val-negative">${(s.max_drawdown_pct || 0).toFixed(1)}%</td>
            </tr>
        `).join('');
    } catch (e) { console.error('Leaderboard error:', e); }
}

// ─── Vault Search ───────────────────────────────────────────────
async function searchVault() {
    const q = document.getElementById('vaultSearchInput').value.trim();
    try {
        const res = await fetch(`/api/vault/search?q=${encodeURIComponent(q)}&limit=50`);
        const data = await res.json();
        const tbody = document.getElementById('vaultBody');
        if (!data.results || data.results.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Kho lưu trữ đang trống. Hãy upload tài liệu hoặc dùng Spider để tải bài báo mới.</td></tr>`;
            return;
        }
        tbody.innerHTML = data.results.map(r => {
            const typeClass = (r.type || '').includes('PAPER') ? 'badge-paper' : 'badge-blog';
            return `
            <tr>
                <td style="font-family:var(--font-mono);font-size:11px">${r.id || ''}</td>
                <td style="max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:var(--font-main)">${r.title || ''}</td>
                <td><span class="badge ${typeClass}">${r.type || ''}</span></td>
                <td>${(r.created_at || '').substring(0, 10)}</td>
                <td><button class="btn btn-secondary btn-sm" onclick="viewEntry('${r.id}')"><i class="fa-solid fa-eye"></i></button></td>
            </tr>`;
        }).join('');
    } catch (e) { console.error('Vault search error:', e); }
}

let currentRawText = '';

function setElemText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

async function viewEntry(id) {
    try {
        const res = await fetch(`/api/vault/entry/${id}`);
        const data = await res.json();
        if (data.entry) {
            const e = data.entry;
            
            // Check if modal element exists in DOM
            const modal = document.getElementById('vaultModal');
            if (!modal) {
                // If user has not refreshed the HTML page yet, give fallback alert
                alert(`📄 ${e.title}\n\nType: ${e.type}\nID: ${e.id}\nDate: ${e.created_at}\n\n📌 TÓM TẮT:\n${e.note || ''}\n\n(💡 Hãy bấm phím F5 hoặc Ctrl+Shift+R để tải giao diện Modal mới!)`);
                return;
            }

            // Populate Modal Header
            setElemText('modalTypeBadge', e.type || 'DOCUMENT');
            setElemText('modalTitle', e.title || 'Untitled');
            setElemText('modalId', `ID: ${e.id}`);
            setElemText('modalDate', (e.created_at || '').substring(0, 19).replace('T', ' '));
            setElemText('modalWeb', e.web ? `Nguồn: ${e.web}` : 'Local Ingestion');

            // Populate Tab 1: Summary / Insights
            setElemText('modalSummaryContent', e.note || 'Không có tóm tắt chi tiết.');

            // Populate Tab 2: Full Raw Text
            currentRawText = e.ctx || '';
            setElemText('modalRawContent', currentRawText || '[Không có nội dung văn bản gốc]');
            
            const words = currentRawText ? currentRawText.trim().split(/\s+/).length : 0;
            const chars = currentRawText ? currentRawText.length : 0;
            setElemText('modalRawWordCount', `📊 Độ dài: ${words.toLocaleString()} từ • ${chars.toLocaleString()} ký tự`);

            // Populate Tab 3: Metadata
            const metaEl = document.getElementById('modalMetaContent');
            if (metaEl) {
                try {
                    const parsedMeta = typeof e.metadata === 'string' ? JSON.parse(e.metadata) : e.metadata;
                    metaEl.textContent = JSON.stringify(parsedMeta, null, 2);
                } catch (err) {
                    metaEl.textContent = e.metadata || '{}';
                }
            }

            // Reset to Tab 1 & Open Modal
            switchModalTab('summary');
            modal.classList.add('active');
        }
    } catch (err) { 
        console.error(err); 
        alert('Lỗi tải tài liệu: ' + err.message);
    }
}

function closeVaultModal() {
    const modal = document.getElementById('vaultModal');
    if (modal) modal.classList.remove('active');
}

function switchModalTab(tabName) {
    document.querySelectorAll('.modal-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.modalTab === tabName);
    });
    document.querySelectorAll('.modal-tab-content').forEach(content => {
        content.classList.remove('active');
    });
    const target = document.getElementById(`modalTab-${tabName}`);
    if (target) target.classList.add('active');
}

function copyRawText() {
    if (!currentRawText) return;
    navigator.clipboard.writeText(currentRawText).then(() => {
        alert('✅ Đã sao chép toàn bộ văn bản gốc vào clipboard!');
    }).catch(err => {
        console.error('Copy failed:', err);
    });
}

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeVaultModal();
});

// ─── Spider Control ─────────────────────────────────────────────
async function runSpider(dryRun) {
    const logEl = document.getElementById('executionLog');
    logEl.textContent = dryRun ? '🔍 Running Spider Dry Run...\n' : '🕷️ Running Spider Scrape & Download...\n';
    try {
        const res = await fetch('/api/spider/run', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ dry_run: dryRun, auto_run: false, use_ai: false })
        });
        const data = await res.json();
        logEl.textContent += data.output || data.message || 'Done.';
        if (data.errors) logEl.textContent += '\n⚠ ' + data.errors;
        loadLeaderboard();
    } catch (e) { logEl.textContent += '\n❌ Error: ' + e.message; }
}

async function runAlpha(useAI) {
    const logEl = document.getElementById('executionLog');
    logEl.textContent = useAI ? '🧠 Running Alpha Factory with AI...\n' : '⚡ Running Alpha Factory (Semantic)...\n';
    try {
        const res = await fetch('/api/alpha/run', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ paper: '', use_ai: useAI })
        });
        const data = await res.json();
        logEl.textContent += data.output || data.message || 'Done.';
        if (data.errors) logEl.textContent += '\n⚠ ' + data.errors;
        loadLeaderboard();
    } catch (e) { logEl.textContent += '\n❌ Error: ' + e.message; }
}

async function runKeywordDiscovery() {
    const q = document.getElementById('keywordDiscoveryInput').value.trim();
    if (!q) return;
    const logEl = document.getElementById('executionLog');
    logEl.textContent = `🌍 Đang truy vấn Mạng lưới Học thuật (arXiv, CrossRef) cho từ khóa: "${q}"...\n`;
    try {
        const res = await fetch('/api/research/keyword', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ query: q })
        });
        const data = await res.json();
        if (data.status === 'success') {
            logEl.textContent += `✅ Thành công! Đã tìm thấy và lưu trữ bài báo vào Vault.\n`;
            logEl.textContent += `Tiêu đề: ${data.title}\nID: ${data.id}\nĐã lưu dạng Raw Text.\n\nBây giờ bạn có thể mở Tab "Paper Vault" để xem chi tiết, hoặc bấm "Run Alpha Factory" để bóc tách chiến lược!`;
            searchVault(); // refresh vault
        } else {
            logEl.textContent += `❌ Lỗi: ${data.message}`;
        }
    } catch (e) { logEl.textContent += '\n❌ Error: ' + e.message; }
}

// ─── Upload ─────────────────────────────────────────────────────
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');

uploadZone.addEventListener('click', () => fileInput.click());
uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('dragover'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', (e) => {
    e.preventDefault(); uploadZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => { if (fileInput.files.length) uploadFile(fileInput.files[0]); });

async function uploadFile(file) {
    const resultEl = document.getElementById('uploadResult');
    resultEl.style.display = 'block';
    resultEl.textContent = `⏳ Uploading ${file.name} (${(file.size/1024).toFixed(1)} KB)...`;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/research/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.status === 'success') {
            resultEl.innerHTML = `✅ <strong>${data.title || file.name}</strong> uploaded successfully!<br>ID: <code>${data.id}</code> | Words: ${data.word_count || 0}`;
        } else {
            resultEl.textContent = `❌ Error: ${data.message}`;
            resultEl.style.background = 'rgba(248,113,113,0.08)';
            resultEl.style.borderColor = 'rgba(248,113,113,0.2)';
            resultEl.style.color = '#f87171';
        }
    } catch (e) { resultEl.textContent = `❌ Upload failed: ${e.message}`; }
    loadInbox();
}

// ─── Inbox List ─────────────────────────────────────────────────
async function loadInbox() {
    try {
        const res = await fetch('/api/inbox/list');
        const data = await res.json();
        const container = document.getElementById('inboxList');
        if (!data.files || data.files.length === 0) {
            container.innerHTML = '<div class="empty-state" style="padding:20px;font-size:13px;color:#64748b">Inbox trống. Upload hoặc chạy Spider để thêm paper.</div>';
            return;
        }
        container.innerHTML = data.files.map(f => `
            <div class="inbox-item">
                <span><i class="fa-solid fa-file-pdf" style="color:#f87171;margin-right:8px"></i>${f.name}</span>
                <span class="file-size">${f.size_kb} KB</span>
            </div>
        `).join('');
    } catch (e) { console.error(e); }
}

// ─── Settings: Toggle & Scheduler ───────────────────────────────
async function loadSettings() {
    try {
        const res = await fetch('/api/spider/settings');
        const data = await res.json();
        if (data.status === 'success') {
            const s = data.settings;
            const toggle = document.getElementById('modeToggle');
            const label = document.getElementById('toggleLabelText');
            const hint = document.getElementById('modeHint');
            const timeInput = document.getElementById('scheduleTime');

            if (s.scraping_mode === 'OPEN_DISCOVERY') {
                toggle.checked = true;
                label.textContent = 'AI Tự động Khám phá';
                hint.textContent = 'AI sẽ tự sinh từ khóa và lên mạng tìm kiếm tài liệu tài chính mới mỗi ngày.';
            } else {
                toggle.checked = false;
                label.textContent = 'Thu thập Link cố định';
                hint.textContent = 'Spider sẽ quét các nguồn web đã cấu hình sẵn (arXiv, SSRN, Quantocracy).';
            }
            if (s.schedule_time) timeInput.value = s.schedule_time;
        }

        // Lấy thông tin trạng thái hoạt động thực tế của Scheduler
        const statusRes = await fetch('/api/scheduler/status');
        const statusData = await statusRes.json();
        if (statusData.status === 'success') {
            const badge = document.getElementById('schedulerStatusBadge');
            const info = document.getElementById('lastRunInfo');
            if (badge) {
                if (statusData.service_active) {
                    badge.style.background = 'rgba(52,211,153,0.15)';
                    badge.style.color = 'var(--accent-green)';
                    badge.innerHTML = '<i class="fa-solid fa-circle-dot"></i> Đang Chạy Tự Động';
                } else {
                    badge.style.background = 'rgba(239,68,68,0.15)';
                    badge.style.color = '#f87171';
                    badge.innerHTML = '<i class="fa-solid fa-circle-pause"></i> Tạm Dừng';
                }
            }
            if (info) {
                if (statusData.last_run_time) {
                    info.textContent = `${statusData.last_run_date} lúc ${statusData.last_run_time}`;
                } else {
                    info.textContent = 'Chưa chạy lần nào hôm nay';
                }
            }
        }
    } catch (e) { console.error('Load settings error:', e); }
}

function toggleMode() {
    const toggle = document.getElementById('modeToggle');
    const label = document.getElementById('toggleLabelText');
    const hint = document.getElementById('modeHint');
    if (toggle.checked) {
        label.textContent = 'AI Tự động Khám phá';
        hint.textContent = 'AI sẽ tự sinh từ khóa và lên mạng tìm kiếm tài liệu tài chính mới mỗi ngày.';
    } else {
        label.textContent = 'Thu thập Link cố định';
        hint.textContent = 'Spider sẽ quét các nguồn web đã cấu hình sẵn (arXiv, SSRN, Quantocracy).';
    }
    saveSettings();
}

async function saveSettings() {
    const mode = document.getElementById('modeToggle').checked ? 'OPEN_DISCOVERY' : 'TARGETED_LINKS';
    const time = document.getElementById('scheduleTime').value;
    const logEl = document.getElementById('executionLog');
    try {
        const res = await fetch('/api/spider/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ scraping_mode: mode, schedule_time: time })
        });
        const data = await res.json();
        logEl.textContent = `✅ Cấu hình đã lưu!\n  Chế độ: ${mode === 'OPEN_DISCOVERY' ? 'AI Tự động Khám phá' : 'Thu thập Link cố định'}\n  Khung giờ: ${time}`;
    } catch (e) { logEl.textContent = '❌ Lỗi lưu cấu hình: ' + e.message; }
}

async function runSchedulerNow() {
    const logEl = document.getElementById('executionLog');
    const mode = document.getElementById('modeToggle').checked ? 'OPEN_DISCOVERY' : 'TARGETED_LINKS';
    logEl.textContent = mode === 'OPEN_DISCOVERY'
        ? '🌍 Đang chạy: AI Tự Động Khám phá → Alpha Factory...\n'
        : '🕷️ Đang chạy: Spider → Alpha Factory...\n';
    try {
        const res = await fetch('/api/spider/run-pipeline', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({})
        });
        const data = await res.json();
        logEl.textContent += data.output || data.message || 'Done.';
        if (data.errors) logEl.textContent += '\n⚠ ' + data.errors;
        loadLeaderboard();
    } catch (e) { logEl.textContent += '\n❌ Error: ' + e.message; }
}

// ─── Learned Rules Memory ─────────────────────────────────────────
async function loadRules() {
    const tbody = document.getElementById('rulesBody');
    if (!tbody) return;
    try {
        const res = await fetch('/api/rules/list');
        const data = await res.json();
        if (data.stats && document.getElementById('statRules')) {
            document.getElementById('statRules').textContent = data.stats.total_rules || 0;
        }
        if (!data.rules || data.rules.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Chưa có Rule nào được học. Khi chạy Alpha Factory, AI sẽ tự động đúc kết Rule vào đây!</td></tr>';
            return;
        }
        tbody.innerHTML = data.rules.map(r => {
            const keywords = Array.isArray(r.trigger_keywords) ? r.trigger_keywords : [];
            const kwBadges = keywords.slice(0, 5).map(k => `<span class="badge badge-paper" style="font-size:10px;margin-right:4px">${k}</span>`).join('');
            
            const payload = r.rule_payload || {};
            const payloadSummary = `<strong>${payload.model_type || 'Model'}</strong> (${payload.symbol || 'SYM'} • ${payload.timeframe || '1d'}) | Window: ${payload.rolling_window || 20}, Thresh: ${payload.threshold_val || 0}`;

            return `
            <tr>
                <td style="font-family:var(--font-mono);font-size:11px;font-weight:700;color:var(--accent-purple)">${r.id}</td>
                <td>
                    <strong style="color:var(--text-primary)">${r.name}</strong>
                    <div style="font-size:11px;color:var(--text-muted);margin-top:2px">Nguồn: ${r.source_id || 'Self-Learned'}</div>
                </td>
                <td style="max-width:280px">${kwBadges}${keywords.length > 5 ? `<span style="font-size:10px;color:var(--text-muted)">+${keywords.length - 5}</span>` : ''}</td>
                <td style="font-size:12px;font-family:var(--font-mono);color:var(--accent-cyan)">${payloadSummary}</td>
                <td><span class="badge" style="background:rgba(52,211,153,0.15);color:var(--accent-green)">${Math.round((r.confidence || 0.9) * 100)}%</span></td>
                <td><strong style="color:var(--accent-orange);font-family:var(--font-mono)">${r.hit_count || 0} hits</strong></td>
            </tr>`;
        }).join('');
    } catch (e) {
        console.error('Error loading rules:', e);
        if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Lỗi tải dữ liệu luật: ${e.message}</td></tr>`;
    }
}

// ─── Strategy Components Store ─────────────────────────────────────
async function loadComponents() {
    const tbody = document.getElementById('componentsBody');
    if (!tbody) return;
    try {
        const res = await fetch('/api/components/list');
        const data = await res.json();
        if (!data.components || data.components.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Chưa có thành phần chiến lược nào. Hãy chạy Alpha Factory để trích xuất code và công thức!</td></tr>';
            return;
        }
        tbody.innerHTML = data.components.map(c => {
            const codeObj = c.code_snippets || {};
            const codeLang = codeObj.lang || 'python';
            const codePreview = (codeObj.python || codeObj.cpp || codeObj.code || '// No code').slice(0, 140);
            
            const params = c.parameters || {};
            const threshOpen = params.threshold_open || params.threshold_val || '-';
            const win = params.rolling_window || '-';
            const kappa = params.min_kappa_speed ? ` • κ ≥ ${params.min_kappa_speed}` : '';
            const fee = params.fee_rate ? ` • Fee: ${(params.fee_rate * 100).toFixed(2)}%` : '';
            const paramsStr = `<div style="color:#e2e8f0;font-weight:600">Window: ${win}d | Open: ±${threshOpen}</div><div style="color:var(--text-muted);font-size:10px;margin-top:2px">Exit: [L: ${params.threshold_close_long || '-'}, S: ${params.threshold_close_short || '-'}]${kappa}${fee}</div>`;

            return `
            <tr>
                <td style="font-family:var(--font-mono);font-size:11px;font-weight:700;color:var(--accent-cyan)">${c.id}</td>
                <td>
                    <strong style="color:var(--text-primary)">${c.strategy_name}</strong>
                    <div style="font-size:11px;color:var(--text-muted);margin-top:2px">Paper: <span style="color:var(--accent-purple);font-weight:600">${c.vault_id}</span> • ${c.timeframe || '1d'} • ${c.asset_class || 'equities'}</div>
                </td>
                <td><span class="badge badge-paper">${c.model_family}</span></td>
                <td>
                    <div style="background:rgba(0,0,0,0.4);border:1px solid rgba(255,255,255,0.08);padding:6px 10px;border-radius:6px;font-family:var(--font-mono);font-size:11px;color:#a5f3fc;max-width:320px;white-space:pre-wrap;overflow:hidden;text-overflow:ellipsis;">
                        <span style="color:#f472b6;font-weight:bold">[${codeLang}]</span>\n${codePreview}
                    </div>
                </td>
                <td style="font-size:11px;font-family:var(--font-mono);">${paramsStr}</td>
                <td><span class="badge" style="background:rgba(52,211,153,0.15);color:var(--accent-green)"><i class="fa-solid fa-circle-check"></i> ${c.backtest_status}</span></td>
            </tr>`;
        }).join('');
    } catch (e) {
        console.error('Error loading components:', e);
        if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Lỗi tải dữ liệu components: ${e.message}</td></tr>`;
    }
}

// ─── Crawler Site Templates ────────────────────────────────────────
async function loadTemplates() {
    const tbody = document.getElementById('templatesBody');
    if (!tbody) return;
    try {
        const res = await fetch('/api/templates/list');
        const data = await res.json();
        if (!data.templates || data.templates.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Chưa có Template nào. Hệ thống sẽ tự động học khi cào các trang web mới!</td></tr>';
            return;
        }
        tbody.innerHTML = data.templates.map(t => {
            const noiseList = Array.isArray(t.noise_selectors) ? t.noise_selectors : [];
            return `
            <tr>
                <td style="font-family:var(--font-mono);font-size:11px;font-weight:700;color:var(--accent-orange)">${t.id}</td>
                <td><strong style="color:var(--text-primary)">${t.domain_pattern}</strong></td>
                <td><span class="badge badge-paper">${t.cms_type || 'Custom'}</span></td>
                <td style="font-size:11px;font-family:var(--font-mono);color:#93c5fd">
                    <div>Title: <code>${t.title_selector || '-'}</code></div>
                    <div style="margin-top:2px">Body: <code>${t.content_selector || '-'}</code></div>
                </td>
                <td style="font-size:10px;color:var(--text-muted);font-family:var(--font-mono)">${noiseList.slice(0, 3).join(', ')}${noiseList.length > 3 ? ` (+${noiseList.length - 3})` : ''}</td>
                <td><strong style="color:var(--accent-purple);font-family:var(--font-mono)">${t.hit_count || 0} hits</strong></td>
            </tr>`;
        }).join('');
    } catch (e) {
        console.error('Error loading templates:', e);
        if (tbody) tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Lỗi tải templates: ${e.message}</td></tr>`;
    }
}

// ─── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadLeaderboard();
    loadInbox();
    searchVault();
    loadRules();
    loadComponents();
    loadTemplates();
    loadSettings();
});

