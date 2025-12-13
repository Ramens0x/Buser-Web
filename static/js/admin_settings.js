$(document).ready(function () {
    // Chỉ chạy nếu có form cài đặt
    if ($('#settings-form').length === 0) return;

    var adminBanks = [];
    var supportedBanks = [];
    const SYSTEM_COINS = ['bustabit', 'ether', 'usdt', 'usdc', 'bnb', 'sol', 'itlg', 'itl'];

    // --- 1. HÀM LOAD DỮ LIỆU TỪ SERVER ---
    function loadSettings() {
        $.ajax({
            url: API_URL + "/api/admin/settings",
            type: 'GET',
            success: function (response) {
                if (response.success) {
                    const s = response.settings;

                    // A. Điền các trường đơn giản (Input/Select/Textarea)
                    // Tự động quét tất cả input có name để điền giá trị tương ứng từ response
                    $('#settings-form').find('input, select, textarea').each(function () {
                        const name = $(this).attr('name');
                        // 1. Check trong settings gốc
                        if (s[name] !== undefined) {
                            $(this).val(s[name]);
                        }
                        // 2. Check trong coin_fees (nếu tên dạng fee_xxx_amount)
                        else if (name.startsWith('fee_')) {
                            const parts = name.split('_'); // fee, bustabit, amount
                            if (parts.length === 3 && s.coin_fees) {
                                const coin = parts[1];
                                const type = parts[2]; // amount hoặc threshold
                                const coinData = s.coin_fees[coin];

                                if (coinData) {
                                    // Nếu lưu dạng object {fee:..., threshold:...}
                                    if (typeof coinData === 'object') {
                                        if (type === 'amount') $(this).val(coinData.fee);
                                        if (type === 'threshold') $(this).val(coinData.threshold);
                                    }
                                    // Nếu lưu dạng số (legacy) -> chỉ là fee
                                    else if (type === 'amount') {
                                        $(this).val(coinData);
                                    }
                                }
                            }
                        }
                    });

                    // B. Xử lý dữ liệu Ngân hàng (Nếu có bảng)
                    if ($('#bank-list-table').length > 0) {
                        if (s.admin_banks && Array.isArray(s.admin_banks)) {
                            adminBanks = s.admin_banks;
                        } else if (s.admin_bank_bin) {
                            // Fallback dữ liệu cũ
                            adminBanks = [{
                                bank_name: "Ngân hàng mặc định",
                                bin: s.admin_bank_bin,
                                acc: s.admin_account_number,
                                name: s.admin_account_name,
                                coins: []
                            }];
                        }
                        renderBankTable();
                    }

                    if ($('#supported-bank-table').length > 0) {
                        supportedBanks = s.supported_banks || [];
                        renderSupportedBanks();
                    }
                }
            },
            error: function (xhr) {
                alert("Lỗi tải cài đặt: " + xhr.responseJSON.message);
            }
        });
    }

    // --- 2. CÁC HÀM RENDER & XỬ LÝ BẢNG (Global functions) ---
    // Phải gán vào window để gọi được từ onclick trong HTML

    window.renderBankTable = function () {
        const tbody = $('#bank-list-table tbody');
        tbody.empty();

        if (adminBanks.length === 0) {
            tbody.append('<tr><td colspan="6" class="text-center">Chưa có ngân hàng nào. Hãy thêm mới.</td></tr>');
            return;
        }

        adminBanks.forEach((bank, index) => {
            let currentCoins = bank.coins || [];

            // Tạo checkbox coins
            let coinChecksHtml = '<div style="display:flex; flex-wrap:wrap; gap:10px;">';
            SYSTEM_COINS.forEach(coin => {
                let isChecked = currentCoins.includes(coin) ? 'checked' : '';
                let coinLabel = coin.toUpperCase();
                if (coin === 'bustabit') coinLabel = 'BTC';
                if (coin === 'ether') coinLabel = 'ETH';

                coinChecksHtml += `
                    <label style="font-weight:normal; font-size:12px; cursor:pointer;">
                        <input type="checkbox" onchange="toggleBankCoin(${index}, '${coin}', this.checked)" ${isChecked}> ${coinLabel}
                    </label>`;
            });
            coinChecksHtml += '</div>';

            const row = `
                <tr>
                    <td><input type="text" class="form-control input-sm" value="${escapeHTML(bank.bank_name)}" onchange="updateBank(${index}, 'bank_name', this.value)" placeholder="Tên Bank"></td>
                    <td><input type="text" class="form-control input-sm" value="${escapeHTML(bank.bin)}" onchange="updateBank(${index}, 'bin', this.value)" placeholder="BIN"></td>
                    <td><input type="text" class="form-control input-sm" value="${escapeHTML(bank.acc)}" onchange="updateBank(${index}, 'acc', this.value)" placeholder="Số TK"></td>
                    <td><input type="text" class="form-control input-sm" value="${escapeHTML(bank.name)}" onchange="updateBank(${index}, 'name', this.value)" placeholder="Chủ TK"></td>
                    <td>${coinChecksHtml}</td>
                    <td><button type="button" class="btn btn-danger btn-xs" onclick="removeBank(${index})"><i class="fa fa-trash"></i></button></td>
                </tr>`;
            tbody.append(row);
        });
    };

    window.updateBank = function (index, field, value) {
        if (adminBanks[index]) adminBanks[index][field] = value;
    };

    window.removeBank = function (index) {
        if (!confirm("Xóa ngân hàng này?")) return;
        adminBanks.splice(index, 1);
        renderBankTable();
    };

    window.toggleBankCoin = function (index, coin, isChecked) {
        if (!adminBanks[index].coins) adminBanks[index].coins = [];
        if (isChecked) {
            if (!adminBanks[index].coins.includes(coin)) adminBanks[index].coins.push(coin);
        } else {
            adminBanks[index].coins = adminBanks[index].coins.filter(c => c !== coin);
        }
    };

    window.renderSupportedBanks = function () {
        const tbody = $('#supported-bank-table tbody');
        tbody.empty();
        supportedBanks.forEach((bank, index) => {
            const row = `
                <tr>
                    <td><input type="text" class="form-control input-sm" value="${escapeHTML(bank.name)}" onchange="updateSupBank(${index}, 'name', this.value)"></td>
                    <td><input type="text" class="form-control input-sm" value="${escapeHTML(bank.short_name)}" onchange="updateSupBank(${index}, 'short_name', this.value)"></td>
                    <td><input type="text" class="form-control input-sm" value="${escapeHTML(bank.bin)}" onchange="updateSupBank(${index}, 'bin', this.value)"></td>
                    <td><button type="button" class="btn btn-danger btn-xs" onclick="removeSupBank(${index})"><i class="fa fa-trash"></i></button></td>
                </tr>`;
            tbody.append(row);
        });
    };

    window.updateSupBank = function (index, field, value) { supportedBanks[index][field] = value; };
    window.removeSupBank = function (index) { supportedBanks.splice(index, 1); renderSupportedBanks(); };

    // --- 3. SỰ KIỆN NÚT THÊM ---
    $('#btn-add-bank').click(function () {
        adminBanks.push({ bank_name: "", bin: "", acc: "", name: "", coins: [] });
        renderBankTable();
    });

    $('#btn-add-supported-bank').click(function () {
        supportedBanks.push({ name: "", short_name: "", bin: "" });
        renderSupportedBanks();
    });

    // --- 4. LOGIC SUBMIT FORM (CẬP NHẬT TỪNG PHẦN) ---
    $('#settings-form').on('submit', function (e) {
        e.preventDefault();
        var settingsData = {};

        // A. Quét các trường Input đơn lẻ
        var simpleFields = [
            'maintenance_mode', 'fee_html_content',
            'telegram_bot_token', 'telegram_chat_id',
            'admin_bustabit_id', 'admin_ether_id', 'admin_usdt_wallet', 'admin_usdc_wallet', 'admin_bnb_wallet', 'admin_sol_wallet',
            'admin_itlg_name', 'admin_itlg_wallet', 'admin_itlg_price_buy', 'admin_itlg_price_sell',
            'admin_itl_name', 'admin_itl_wallet', 'admin_itl_price_buy', 'admin_itl_price_sell',
            'liquidity_vnd', 'liquidity_usdt', 'liquidity_usdc', 'liquidity_btc', 'liquidity_eth', 'liquidity_bnb', 'liquidity_sol', 'liquidity_itlg', 'liquidity_itl'
        ];

        simpleFields.forEach(function (name) {
            var field = $(`[name="${name}"]`);
            if (field.length > 0) {
                settingsData[name] = field.val();
            }
        });

        // B. Quét Coin Fees (nếu có)
        var coin_fees = {};
        var coins = ['bustabit', 'ether', 'usdt', 'usdc', 'sol', 'bnb', 'itlg', 'itl'];
        var hasFeeUpdate = false;

        coins.forEach(function (coin) {
            var feeInput = $(`input[name="fee_${coin}_amount"]`);
            if (feeInput.length > 0) {
                coin_fees[coin] = {
                    fee: feeInput.val(),
                    threshold: $(`input[name="fee_${coin}_threshold"]`).val()
                };
                hasFeeUpdate = true;
            }
        });
        if (hasFeeUpdate) settingsData.coin_fees = coin_fees;

        // C. Quét Bảng Ngân hàng (nếu có)
        if ($('#bank-list-table').length > 0) {
            settingsData.admin_banks = adminBanks.filter(b => b.bin && b.acc);
            settingsData.supported_banks = supportedBanks;
        }

        // Gửi dữ liệu
        var btn = $(this).find('button[type="submit"]');
        var originalText = btn.html();
        setLoading(btn, true, 'Đang lưu...');

        $.ajax({
            url: API_URL + "/api/admin/settings",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(settingsData),
            success: function (response) {
                alert(response.message);
                location.reload();
            },
            error: function (xhr) {
                alert("Lỗi: " + (xhr.responseJSON ? xhr.responseJSON.message : "Lỗi kết nối"));
                setLoading(btn, false, originalText); // Restore button
                // Fix lỗi hiển thị lại text cũ
                btn.html(originalText);
            }
        });
    });

    // --- 5. KHỞI CHẠY ---
    loadSettings();
});