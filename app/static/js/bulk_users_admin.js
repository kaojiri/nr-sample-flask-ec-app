/**
 * 一括ユーザー管理システム - 管理画面JavaScript
 */

class BulkUsersAdmin {
    constructor() {
        this.apiBase = '/api/bulk-users';
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadInitialData();
    }

    bindEvents() {
        // ユーザー作成フォーム
        document.getElementById('bulkCreateForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createBulkUsers();
        });

        // 設定テンプレート変更
        document.getElementById('configTemplate').addEventListener('change', (e) => {
            this.toggleCustomConfig(e.target.value === 'custom');
        });

        // 同期操作
        document.getElementById('syncToLoadTesterBtn').addEventListener('click', () => {
            this.syncToLoadTester();
        });

        document.getElementById('checkSyncStatusBtn').addEventListener('click', () => {
            this.checkSyncStatus();
        });

        // ライフサイクル管理
        document.getElementById('cleanupBtn').addEventListener('click', () => {
            this.showConfirmModal('選択したバッチのユーザーを削除しますか？', () => {
                this.cleanupBatch();
            });
        });

        document.getElementById('getCleanupCandidatesBtn').addEventListener('click', () => {
            this.getCleanupCandidates();
        });

        document.getElementById('identifyUsersBtn').addEventListener('click', () => {
            this.identifyUsers();
        });

        document.getElementById('generateReportBtn').addEventListener('click', () => {
            this.generateReport();
        });

        // 設定管理
        document.getElementById('loadTemplateBtn').addEventListener('click', () => {
            this.loadTemplate();
        });

        document.getElementById('saveTemplateBtn').addEventListener('click', () => {
            this.saveTemplate();
        });

        document.getElementById('deleteTemplateBtn').addEventListener('click', () => {
            this.deleteTemplate();
        });

        document.getElementById('validateConfigBtn').addEventListener('click', () => {
            this.validateConfig();
        });

        // タブ切り替え時のデータ更新
        document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
            tab.addEventListener('shown.bs.tab', (e) => {
                const target = e.target.getAttribute('data-bs-target');
                this.onTabChange(target);
            });
        });
    }

    async loadInitialData() {
        await this.loadStats();
        await this.loadConfigTemplates();
        await this.loadBatches();
    }

    toggleCustomConfig(show) {
        const section = document.getElementById('customConfigSection');
        section.style.display = show ? 'block' : 'none';
    }

    async createBulkUsers() {
        const count = parseInt(document.getElementById('userCount').value);
        const template = document.getElementById('configTemplate').value;
        
        let config = {};
        
        if (template === 'custom') {
            config = {
                username_pattern: document.getElementById('usernamePattern').value,
                email_domain: document.getElementById('emailDomain').value,
                password: document.getElementById('defaultPassword')?.value || "TestUser2024!",
                batch_size: parseInt(document.getElementById('batchSize').value)
            };
        } else {
            // テンプレートから設定を取得
            const templateData = await this.getTemplate(template);
            if (templateData) {
                config = templateData.config;
            }
        }

        const btn = document.getElementById('createUsersBtn');
        const originalText = btn.innerHTML;
        
        try {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 作成中...';
            
            this.showProgress(true);
            
            const response = await fetch(`${this.apiBase}/create`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    count: count,
                    config: config
                })
            });

            const result = await response.json();
            
            if (response.ok) {
                this.displayCreateResults(result);
                await this.loadStats(); // 統計情報を更新
                await this.loadBatches(); // バッチ一覧を更新
            } else {
                this.showError('ユーザー作成エラー', result.error);
            }
        } catch (error) {
            this.showError('通信エラー', error.message);
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
            this.showProgress(false);
        }
    }

    displayCreateResults(result) {
        const resultsDiv = document.getElementById('createResults');
        
        let html = `
            <div class="alert alert-${result.successful_count > 0 ? 'success' : 'danger'}">
                <h6><i class="fas fa-info-circle"></i> 作成結果</h6>
                <ul class="mb-0">
                    <li>バッチID: <code>${result.batch_id}</code></li>
                    <li>要求数: ${result.total_requested}</li>
                    <li>成功: ${result.successful_count}</li>
                    <li>失敗: ${result.failed_count}</li>
                    <li>実行時間: ${result.execution_time.toFixed(2)}秒</li>
                </ul>
            </div>
        `;

        if (result.failed_users && result.failed_users.length > 0) {
            html += `
                <div class="alert alert-warning">
                    <h6><i class="fas fa-exclamation-triangle"></i> 失敗したユーザー</h6>
                    <ul class="mb-0">
            `;
            result.failed_users.forEach(user => {
                html += `<li>${user.username}: ${user.error}</li>`;
            });
            html += `</ul></div>`;
        }

        resultsDiv.innerHTML = html;
    }

    showProgress(show) {
        const progressDiv = document.getElementById('createProgress');
        progressDiv.style.display = show ? 'block' : 'none';
        
        if (show) {
            const progressBar = progressDiv.querySelector('.progress-bar');
            progressBar.style.width = '100%';
        }
    }

    async syncToLoadTester() {
        const batchId = document.getElementById('syncBatchId').value;
        const testUsersOnly = document.getElementById('testUsersOnly').checked;
        
        const filterCriteria = {
            test_users_only: testUsersOnly
        };
        
        if (batchId) {
            filterCriteria.batch_id = batchId;
        }

        try {
            const response = await fetch(`${this.apiBase}/sync`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    target: 'load_tester',
                    filter_criteria: filterCriteria
                })
            });

            const result = await response.json();
            this.displaySyncResults(result);
            
        } catch (error) {
            this.showError('同期エラー', error.message);
        }
    }

    async checkSyncStatus() {
        const batchId = document.getElementById('syncBatchId').value;
        
        try {
            let url = `${this.apiBase}/sync/status`;
            if (batchId) {
                url += `?batch_id=${encodeURIComponent(batchId)}`;
            }
            
            const response = await fetch(url);
            const result = await response.json();
            
            this.displaySyncResults({
                success: result.is_valid,
                message: `同期状況: ${result.is_valid ? '正常' : '不整合あり'}`,
                details: result
            });
            
        } catch (error) {
            this.showError('同期状況確認エラー', error.message);
        }
    }

    displaySyncResults(result) {
        const resultsDiv = document.getElementById('syncResults');
        
        let html = `
            <div class="alert alert-${result.success ? 'success' : 'danger'}">
                <h6><i class="fas fa-sync"></i> 同期結果</h6>
        `;
        
        if (result.synced_count !== undefined) {
            html += `
                <ul class="mb-0">
                    <li>同期数: ${result.synced_count}</li>
                    <li>失敗数: ${result.failed_count || 0}</li>
                    <li>実行時間: ${result.duration ? result.duration.toFixed(2) + '秒' : 'N/A'}</li>
                </ul>
            `;
        }
        
        if (result.message) {
            html += `<p class="mb-0">${result.message}</p>`;
        }
        
        if (result.errors && result.errors.length > 0) {
            html += `
                <div class="mt-2">
                    <strong>エラー:</strong>
                    <ul class="mb-0">
            `;
            result.errors.forEach(error => {
                html += `<li>${error}</li>`;
            });
            html += `</ul></div>`;
        }
        
        html += `</div>`;
        resultsDiv.innerHTML = html;
    }

    async cleanupBatch() {
        const batchId = document.getElementById('cleanupBatchId').value;
        const syncCleanup = document.getElementById('syncCleanup').checked;
        
        if (!batchId) {
            this.showError('エラー', 'バッチIDを選択してください');
            return;
        }

        try {
            const endpoint = syncCleanup ? '/lifecycle/sync-cleanup' : '/batches/' + encodeURIComponent(batchId);
            const method = syncCleanup ? 'POST' : 'DELETE';
            const body = syncCleanup ? JSON.stringify({ batch_id: batchId }) : null;
            
            const response = await fetch(`${this.apiBase}${endpoint}`, {
                method: method,
                headers: body ? { 'Content-Type': 'application/json' } : {},
                body: body
            });

            const result = await response.json();
            this.displayCleanupResults(result);
            
            // 統計情報とバッチ一覧を更新
            await this.loadStats();
            await this.loadBatches();
            
        } catch (error) {
            this.showError('クリーンアップエラー', error.message);
        }
    }

    displayCleanupResults(result) {
        const resultsDiv = document.getElementById('cleanupResults');
        
        let html = `
            <div class="alert alert-${result.success ? 'success' : 'warning'}">
                <h6><i class="fas fa-broom"></i> クリーンアップ結果</h6>
        `;
        
        if (result.deleted_count !== undefined) {
            html += `<p>削除されたユーザー数: ${result.deleted_count}</p>`;
        }
        
        if (result.main_application) {
            html += `
                <div class="mb-2">
                    <strong>Main Application:</strong> ${result.main_application.deleted_count}件削除
                </div>
            `;
        }
        
        if (result.load_tester) {
            html += `
                <div class="mb-2">
                    <strong>Load Tester:</strong> 同期${result.load_tester.sync_attempted ? '実行' : '未実行'}
                </div>
            `;
        }
        
        if (result.errors && result.errors.length > 0) {
            html += `
                <div class="mt-2">
                    <strong>エラー:</strong>
                    <ul class="mb-0">
            `;
            result.errors.forEach(error => {
                html += `<li>${error}</li>`;
            });
            html += `</ul></div>`;
        }
        
        html += `</div>`;
        resultsDiv.innerHTML = html;
    }

    async getCleanupCandidates() {
        try {
            const response = await fetch(`${this.apiBase}/lifecycle/cleanup-candidates`);
            const result = await response.json();
            
            if (result.success) {
                this.displayCleanupCandidates(result);
            } else {
                this.showError('候補取得エラー', 'クリーンアップ候補の取得に失敗しました');
            }
        } catch (error) {
            this.showError('通信エラー', error.message);
        }
    }

    displayCleanupCandidates(result) {
        const resultsDiv = document.getElementById('cleanupResults');
        
        let html = `
            <div class="alert alert-info">
                <h6><i class="fas fa-search"></i> クリーンアップ候補</h6>
                <p>古いバッチ数: ${result.total_candidates}</p>
        `;
        
        if (result.candidates && result.candidates.length > 0) {
            html += `
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>バッチID</th>
                                <th>ユーザー数</th>
                                <th>作成日時</th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            result.candidates.forEach(candidate => {
                html += `
                    <tr>
                        <td><code>${candidate.batch_id}</code></td>
                        <td>${candidate.user_count}</td>
                        <td>${new Date(candidate.created_at).toLocaleString()}</td>
                    </tr>
                `;
            });
            
            html += `</tbody></table></div>`;
        } else {
            html += `<p>クリーンアップ候補はありません。</p>`;
        }
        
        html += `</div>`;
        resultsDiv.innerHTML = html;
    }

    async identifyUsers() {
        try {
            const response = await fetch(`${this.apiBase}/lifecycle/identify`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})
            });

            const result = await response.json();
            
            if (result.success) {
                this.displayIdentificationResults(result.identification_result);
            } else {
                this.showError('識別エラー', 'ユーザー識別に失敗しました');
            }
        } catch (error) {
            this.showError('通信エラー', error.message);
        }
    }

    displayIdentificationResults(result) {
        const resultsDiv = document.getElementById('cleanupResults');
        
        let html = `
            <div class="alert alert-info">
                <h6><i class="fas fa-user-check"></i> ユーザー識別結果</h6>
                <ul class="mb-0">
                    <li>テストユーザー: ${result.test_users || 0}件</li>
                    <li>本番ユーザー: ${result.production_users || 0}件</li>
                    <li>不明ユーザー: ${result.unknown_users || 0}件</li>
                </ul>
            </div>
        `;
        
        resultsDiv.innerHTML = html;
    }

    async generateReport() {
        try {
            const response = await fetch(`${this.apiBase}/lifecycle/report`);
            const result = await response.json();
            
            if (result.success) {
                this.displayLifecycleReport(result.lifecycle_report);
            } else {
                this.showError('レポート生成エラー', 'レポート生成に失敗しました');
            }
        } catch (error) {
            this.showError('通信エラー', error.message);
        }
    }

    displayLifecycleReport(report) {
        const resultsDiv = document.getElementById('cleanupResults');
        
        let html = `
            <div class="alert alert-success">
                <h6><i class="fas fa-file-alt"></i> ライフサイクルレポート</h6>
                <div class="row">
                    <div class="col-md-6">
                        <strong>統計情報:</strong>
                        <ul>
                            <li>総ユーザー数: ${report.total_users || 0}</li>
                            <li>テストユーザー数: ${report.test_users || 0}</li>
                            <li>アクティブバッチ数: ${report.active_batches || 0}</li>
                        </ul>
                    </div>
                    <div class="col-md-6">
                        <strong>推奨アクション:</strong>
                        <ul>
        `;
        
        if (report.recommendations) {
            report.recommendations.forEach(rec => {
                html += `<li>${rec}</li>`;
            });
        }
        
        html += `
                        </ul>
                    </div>
                </div>
            </div>
        `;
        
        resultsDiv.innerHTML = html;
    }

    async loadConfigTemplates() {
        try {
            const response = await fetch(`${this.apiBase}/config/templates`);
            const result = await response.json();
            
            if (result.success) {
                this.populateTemplateList(result.templates);
            }
        } catch (error) {
            console.error('テンプレート読み込みエラー:', error);
        }
    }

    populateTemplateList(templates) {
        const select = document.getElementById('templateList');
        select.innerHTML = '<option value="">テンプレートを選択</option>';
        
        templates.forEach(template => {
            const option = document.createElement('option');
            option.value = template.name;
            option.textContent = `${template.name} - ${template.description || ''}`;
            select.appendChild(option);
        });
    }

    async getTemplate(templateName) {
        try {
            const response = await fetch(`${this.apiBase}/config/templates/${encodeURIComponent(templateName)}`);
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.error('テンプレート取得エラー:', error);
        }
        return null;
    }

    async loadTemplate() {
        const templateName = document.getElementById('templateList').value;
        if (!templateName) {
            this.showError('エラー', 'テンプレートを選択してください');
            return;
        }

        try {
            const response = await fetch(`${this.apiBase}/config/templates/${encodeURIComponent(templateName)}`);
            const result = await response.json();
            
            if (result.success) {
                document.getElementById('configEditor').value = JSON.stringify(result.config, null, 2);
                this.showSuccess('テンプレート読み込み完了', `${templateName}を読み込みました`);
            } else {
                this.showError('読み込みエラー', result.error);
            }
        } catch (error) {
            this.showError('通信エラー', error.message);
        }
    }

    async saveTemplate() {
        const templateName = document.getElementById('newTemplateName').value;
        const configText = document.getElementById('configEditor').value;
        
        if (!templateName) {
            this.showError('エラー', 'テンプレート名を入力してください');
            return;
        }
        
        if (!configText) {
            this.showError('エラー', '設定を入力してください');
            return;
        }

        try {
            const config = JSON.parse(configText);
            
            const response = await fetch(`${this.apiBase}/config/templates`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: templateName,
                    config: config
                })
            });

            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('保存完了', `テンプレート "${templateName}" を保存しました`);
                await this.loadConfigTemplates();
                document.getElementById('newTemplateName').value = '';
            } else {
                this.showError('保存エラー', result.errors ? result.errors.join(', ') : '保存に失敗しました');
            }
        } catch (error) {
            if (error instanceof SyntaxError) {
                this.showError('JSON形式エラー', '設定の形式が正しくありません');
            } else {
                this.showError('通信エラー', error.message);
            }
        }
    }

    async deleteTemplate() {
        const templateName = document.getElementById('templateList').value;
        if (!templateName) {
            this.showError('エラー', 'テンプレートを選択してください');
            return;
        }

        this.showConfirmModal(`テンプレート "${templateName}" を削除しますか？`, async () => {
            try {
                const response = await fetch(`${this.apiBase}/config/templates/${encodeURIComponent(templateName)}`, {
                    method: 'DELETE'
                });

                const result = await response.json();
                
                if (result.success) {
                    this.showSuccess('削除完了', `テンプレート "${templateName}" を削除しました`);
                    await this.loadConfigTemplates();
                    document.getElementById('configEditor').value = '';
                } else {
                    this.showError('削除エラー', result.error);
                }
            } catch (error) {
                this.showError('通信エラー', error.message);
            }
        });
    }

    async validateConfig() {
        const configText = document.getElementById('configEditor').value;
        
        if (!configText) {
            this.showError('エラー', '設定を入力してください');
            return;
        }

        try {
            const config = JSON.parse(configText);
            
            const response = await fetch(`${this.apiBase}/config/validate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(config)
            });

            const result = await response.json();
            this.displayConfigValidation(result);
            
        } catch (error) {
            if (error instanceof SyntaxError) {
                this.showError('JSON形式エラー', '設定の形式が正しくありません');
            } else {
                this.showError('通信エラー', error.message);
            }
        }
    }

    displayConfigValidation(result) {
        const validationDiv = document.getElementById('configValidation');
        
        let html = `
            <div class="alert alert-${result.is_valid ? 'success' : 'danger'}">
                <h6><i class="fas fa-${result.is_valid ? 'check' : 'times'}"></i> 検証結果</h6>
                <p>設定は${result.is_valid ? '有効' : '無効'}です</p>
        `;
        
        if (result.errors && result.errors.length > 0) {
            html += `
                <div class="mt-2">
                    <strong>エラー:</strong>
                    <ul class="mb-0">
            `;
            result.errors.forEach(error => {
                html += `<li>${error}</li>`;
            });
            html += `</ul></div>`;
        }
        
        if (result.warnings && result.warnings.length > 0) {
            html += `
                <div class="mt-2">
                    <strong>警告:</strong>
                    <ul class="mb-0">
            `;
            result.warnings.forEach(warning => {
                html += `<li>${warning}</li>`;
            });
            html += `</ul></div>`;
        }
        
        html += `</div>`;
        validationDiv.innerHTML = html;
    }

    async loadStats() {
        try {
            const response = await fetch(`${this.apiBase}/stats`);
            const result = await response.json();
            
            document.getElementById('totalTestUsers').textContent = result.total_test_users || 0;
            document.getElementById('totalBatches').textContent = result.batch_count || 0;
            
            // 同期状況とクリーンアップ候補は別途取得
            await this.updateSyncStatus();
            await this.updateCleanupCandidatesCount();
            
        } catch (error) {
            console.error('統計情報読み込みエラー:', error);
        }
    }

    async updateSyncStatus() {
        try {
            const response = await fetch(`${this.apiBase}/sync/status`);
            const result = await response.json();
            
            document.getElementById('syncStatus').textContent = result.is_valid ? '正常' : '要確認';
        } catch (error) {
            document.getElementById('syncStatus').textContent = 'エラー';
        }
    }

    async updateCleanupCandidatesCount() {
        try {
            const response = await fetch(`${this.apiBase}/lifecycle/cleanup-candidates`);
            const result = await response.json();
            
            document.getElementById('cleanupCandidates').textContent = result.total_candidates || 0;
        } catch (error) {
            document.getElementById('cleanupCandidates').textContent = '-';
        }
    }

    async loadBatches() {
        try {
            const response = await fetch(`${this.apiBase}/stats`);
            const result = await response.json();
            
            this.populateBatchesTable(result.batches || []);
            this.populateCleanupBatchSelect(result.batches || []);
            
        } catch (error) {
            console.error('バッチ情報読み込みエラー:', error);
        }
    }

    populateBatchesTable(batches) {
        const tbody = document.querySelector('#batchesTable tbody');
        
        if (batches.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">バッチがありません</td></tr>';
            return;
        }
        
        tbody.innerHTML = batches.map(batch => `
            <tr>
                <td><code>${batch.batch_id}</code></td>
                <td>${batch.user_count}</td>
                <td>${new Date(batch.created_at).toLocaleString()}</td>
                <td>
                    <button class="btn btn-sm btn-outline-danger" onclick="bulkUsersAdmin.deleteBatch('${batch.batch_id}')">
                        <i class="fas fa-trash"></i> 削除
                    </button>
                </td>
            </tr>
        `).join('');
    }

    populateCleanupBatchSelect(batches) {
        const select = document.getElementById('cleanupBatchId');
        select.innerHTML = '<option value="">バッチを選択してください</option>';
        
        batches.forEach(batch => {
            const option = document.createElement('option');
            option.value = batch.batch_id;
            option.textContent = `${batch.batch_id} (${batch.user_count}ユーザー)`;
            select.appendChild(option);
        });
    }

    async deleteBatch(batchId) {
        this.showConfirmModal(`バッチ "${batchId}" を削除しますか？`, async () => {
            try {
                const response = await fetch(`${this.apiBase}/batches/${encodeURIComponent(batchId)}`, {
                    method: 'DELETE'
                });

                const result = await response.json();
                
                if (result.success) {
                    this.showSuccess('削除完了', `バッチ "${batchId}" を削除しました`);
                    await this.loadStats();
                    await this.loadBatches();
                } else {
                    this.showError('削除エラー', result.error);
                }
            } catch (error) {
                this.showError('通信エラー', error.message);
            }
        });
    }

    onTabChange(target) {
        switch (target) {
            case '#stats':
                this.loadStats();
                this.loadBatches();
                break;
            case '#config':
                this.loadConfigTemplates();
                break;
            case '#lifecycle':
                this.loadBatches();
                break;
        }
    }

    showConfirmModal(message, callback) {
        document.getElementById('confirmMessage').textContent = message;
        
        const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
        modal.show();
        
        // 前のイベントリスナーを削除
        const confirmBtn = document.getElementById('confirmAction');
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        
        // 新しいイベントリスナーを追加
        newConfirmBtn.addEventListener('click', () => {
            modal.hide();
            callback();
        });
    }

    showError(title, message) {
        // Bootstrap Toastを使用してエラーを表示
        this.showToast(title, message, 'danger');
    }

    showSuccess(title, message) {
        // Bootstrap Toastを使用して成功メッセージを表示
        this.showToast(title, message, 'success');
    }

    showToast(title, message, type) {
        // 簡易的なアラート表示（実際のプロジェクトではToastライブラリを使用）
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alertDiv.innerHTML = `
            <strong>${title}</strong><br>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alertDiv);
        
        // 5秒後に自動削除
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.parentNode.removeChild(alertDiv);
            }
        }, 5000);
    }
}

// 初期化
let bulkUsersAdmin;
document.addEventListener('DOMContentLoaded', () => {
    bulkUsersAdmin = new BulkUsersAdmin();
});