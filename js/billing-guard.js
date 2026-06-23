/* ============================================================
   billing-guard.js — 计费、限流防护模块
   Token消耗统计 | 双层限流 | 余额告警 | 用量看板
   ============================================================ */

const BillingGuard = (() => {
  // === Config ===
  const ALERT_THRESHOLDS = {
    low: 0.10,    // $0.10 以下告警
    critical: 0.02, // $0.02 以下锁定
  };

  // === Render Billing Dashboard ===
  function renderDashboard(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const report = DeepSeekAPI.getBillingReport();
    const lang = I18N.getLang();

    container.innerHTML = `
      <div class="billing-dashboard">
        <div class="billing-header">
          <span class="billing-title">📊 ${lang === 'zh' ? 'DeepSeek 用量看板' : 'DeepSeek Usage Dashboard'}</span>
          <span class="status-badge ${report.apiConfigured ? 'success' : 'error'}">
            ${report.apiConfigured ? (lang === 'zh' ? '已连接' : 'Connected') : (lang === 'zh' ? '未配置' : 'Not Configured')}
          </span>
          <span class="billing-env-badge ${report.env}">
            ${report.env === 'production' ? 'PROD' : 'DEV'}
          </span>
        </div>

        <div class="billing-stats">
          <div class="billing-stat">
            <div class="billing-stat-value">${formatTokens(report.totalTokens)}</div>
            <div class="billing-stat-label">${lang === 'zh' ? '总Token' : 'Total Tokens'}</div>
          </div>
          <div class="billing-stat">
            <div class="billing-stat-value">$${report.totalCost}</div>
            <div class="billing-stat-label">${lang === 'zh' ? '预估费用' : 'Est. Cost'}</div>
          </div>
          <div class="billing-stat">
            <div class="billing-stat-value">${report.rpmCurrent}/${report.rpmLimit}</div>
            <div class="billing-stat-label">${lang === 'zh' ? 'RPM (分钟)' : 'RPM (min)'}</div>
          </div>
          <div class="billing-stat">
            <div class="billing-stat-value">${report.freeTokensRemaining.toLocaleString()}</div>
            <div class="billing-stat-label">${lang === 'zh' ? '剩余免费额度' : 'Free Remaining'}</div>
          </div>
        </div>

        <!-- Daily progress bar -->
        <div class="billing-progress-section">
          <div class="billing-progress-label">
            ${lang === 'zh' ? '每日用量' : 'Daily Usage'}: ${report.dailyPercent}%
          </div>
          <div class="billing-progress-bar">
            <div class="billing-progress-fill ${report.dailyPercent > 80 ? 'danger' : report.dailyPercent > 50 ? 'warning' : 'normal'}"
                 style="width:${Math.min(100, report.dailyPercent)}%"></div>
          </div>
          <div class="billing-progress-limit">
            ${formatTokens(report.dailyTokens)} / ${formatTokens(report.dailyLimit)}
          </div>
        </div>

        <!-- Per-model breakdown -->
        ${report.models.length > 0 ? `
        <div class="billing-models">
          <div class="billing-models-title">${lang === 'zh' ? '模型明细' : 'Per Model'}</div>
          ${report.models.map(m => `
            <div class="billing-model-row">
              <span class="billing-model-name">${m.model}</span>
              <span class="billing-model-calls">${m.calls} ${lang === 'zh' ? '次' : 'calls'}</span>
              <span class="billing-model-tokens">${formatTokens(m.inputTokens + m.outputTokens)}</span>
              <span class="billing-model-cost">$${m.cost.toFixed(4)}</span>
            </div>
          `).join('')}
        </div>` : ''}

        <!-- Controls -->
        <div class="billing-actions">
          <button class="btn btn-sm btn-ghost" id="btn-reset-billing">
            🔄 ${lang === 'zh' ? '重置统计' : 'Reset Stats'}
          </button>
          <button class="btn btn-sm btn-ghost" id="btn-toggle-env">
            ⚙ ${lang === 'zh' ? '环境: ' + report.env : 'Env: ' + report.env}
          </button>
        </div>
      </div>`;

    // Bind buttons
    document.getElementById('btn-reset-billing')?.addEventListener('click', () => {
      if (confirm(lang === 'zh' ? '确定重置所有用量统计？' : 'Reset all usage statistics?')) {
        resetStats();
        renderDashboard(containerId);
      }
    });
    document.getElementById('btn-toggle-env')?.addEventListener('click', () => {
      const current = DeepSeekAPI.getEnv();
      const next = current === 'development' ? 'production' : 'development';
      DeepSeekAPI.setEnv(next);
      renderDashboard(containerId);
    });
  }

  // === Check Balance + Show Alert ===
  function checkBalanceAndAlert() {
    const report = DeepSeekAPI.getBillingReport();
    const lang = I18N.getLang();

    // 余额不足锁定
    if (report.env === 'production' && parseFloat(report.totalCost) > 0.50) {
      // 生产环境：超过预估费用$0.50告警
      showBalanceAlert('warning', lang === 'zh'
        ? `本月预估费用已达 $${report.totalCost}，请注意控制用量`
        : `Monthly estimated cost reached $${report.totalCost}. Please monitor usage.`);
    }

    // 每日额度接近上限
    if (report.dailyPercent >= 90) {
      showBalanceAlert('critical', lang === 'zh'
        ? `今日Token用量已达 ${report.dailyPercent}%，即将达到上限`
        : `Daily token usage at ${report.dailyPercent}%, approaching limit.`);
    }

    // 免费额度耗尽
    if (report.freeTokensRemaining <= 0 && report.env === 'development') {
      showBalanceAlert('critical', lang === 'zh'
        ? '免费额度已用完，AI生成功能已临时锁定。请明天再试或切换至生产环境。'
        : 'Free tier exhausted. AI generation locked. Try tomorrow or switch to production.');
      return false;
    }

    return true;
  }

  function showBalanceAlert(type, message) {
    // Remove existing alert
    const existing = document.querySelector('.balance-alert');
    if (existing) existing.remove();

    const alert = document.createElement('div');
    alert.className = `balance-alert balance-alert-${type}`;
    alert.innerHTML = `
      <span>${type === 'critical' ? '🚫' : '⚠️'}</span>
      <span>${message}</span>
      <button class="balance-alert-close">✕</button>`;
    document.body.appendChild(alert);

    alert.querySelector('.balance-alert-close').addEventListener('click', () => alert.remove());
    setTimeout(() => { if (alert.parentNode) alert.remove(); }, 8000);
  }

  // === Before API Call Guard ===
  function preCallGuard() {
    // Check balance
    if (!checkBalanceAndAlert()) {
      return { allowed: false, reason: 'insufficient_balance' };
    }
    return { allowed: true };
  }

  // === Reset ===
  function resetStats() {
    const empty = { total: 0, input: 0, output: 0, byModel: {} };
    localStorage.setItem('deepseek_state', JSON.stringify({
      apiKey: DeepSeekAPI.getApiKey(),
      tokenUsage: empty,
      env: DeepSeekAPI.getEnv(),
    }));
    showToast('用量统计已重置', 'info');
  }

  function formatTokens(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
  }

  function showToast(msg, type) {
    window.App?.showToast?.(msg, type);
  }

  return {
    renderDashboard,
    checkBalanceAndAlert,
    preCallGuard,
    resetStats,
    formatTokens,
  };
})();

window.BillingGuard = BillingGuard;
