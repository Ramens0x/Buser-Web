function numberFormat(number = '0', decimalPlaces = 0) {
    let val = parseFloat(number);
    if (isNaN(val)) return "0";
    let fixed = val.toFixed(decimalPlaces);
    let parts = fixed.split('.');
    let integerPart = parts[0];
    let decimalPart = parts.length > 1 ? parts[1] : '';
    integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');

    if (decimalPlaces > 0) {
        decimalPart = decimalPart.replace(/0+$/, '');
        if (decimalPart.length > 0) {
            return integerPart + '.' + decimalPart;
        }
    }

    return integerPart;
}

function escapeHTML(str) {
    if (str === null || str === undefined) {
        return '';
    }
    return String(str).replace(/[&<>"']/g, function (tag) {
        const chars = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;'
        };
        return chars[tag] || tag;
    });
}

function setLoading(buttonSelector, isLoading, loadingText = 'Đang xử lý...') {
    const btn = $(buttonSelector);
    if (isLoading) {
        btn.data('original-text', btn.html()); // Lưu text cũ
        btn.prop('disabled', true);
        btn.html(`<i class="fa fa-spinner fa-spin"></i> ${loadingText}`);
    } else {
        btn.prop('disabled', false);
        const original = btn.data('original-text');
        if (original) btn.html(original);
    }
}

$(document).ready(function () {

    var csrf_token = $('meta[name=csrf-token]').attr('content');

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrf_token);
            }
            if (settings.global !== false) {
                $('body').append('<div id="ajax-loader" style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;"><i class="fa fa-spinner fa-spin fa-3x" style="color:white;"></i></div>');
            }
        },
        complete: function (xhr, status) {
            // Ẩn Loading
            $('#ajax-loader').remove();
        },
        error: function (xhr) {
            if (xhr.status === 401) {
                alert("⏳ Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại!");
                window.location.href = "login.html";
            }
        }
    });

    let currentMode = 'buy';
    let currentCoin = 'bustabit';
    let isCalculating = false;

    function updatePrices() {
        $.ajax({
            url: API_URL + "/api/prices",
            type: 'GET',
            global: false,
            success: function (data) {

                const showPrice = (price) => {
                    return (price && price > 0) ? numberFormat(price, 0) + ' ₫' : '<span style="font-size:12px; color:#999;">Đang cập nhật</span>';
                };

                if (data.bustabit) {
                    $('#bustabit-buy').html(showPrice(data.bustabit.buy));
                    $('#bustabit-sell').html(showPrice(data.bustabit.sell));
                }

                if (data.ether) {
                    $('#ether-buy').html(showPrice(data.ether.buy));
                    $('#ether-sell').html(showPrice(data.ether.sell));
                }

                if (data.btc) {
                    $('#btc-buy').html(showPrice(data.btc.buy));
                    $('#btc-sell').html(showPrice(data.btc.sell));
                }

                if (data.usdt) {
                    $('#usdt-buy').html(showPrice(data.usdt.buy));
                    $('#usdt-sell').html(showPrice(data.usdt.sell));
                }

                if (data.eth) {
                    $('#eth-buy').html(showPrice(data.eth.buy));
                    $('#eth-sell').html(showPrice(data.eth.sell));
                }

                if (data.bnb) {
                    $('#bnb-buy').html(showPrice(data.bnb.buy));
                    $('#bnb-sell').html(showPrice(data.bnb.sell));
                }

                if (data.sol) {
                    $('#sol-buy').html(showPrice(data.sol.buy));
                    $('#sol-sell').html(showPrice(data.sol.sell));
                }
                updateRateDisplay(data);
            },
            error: function () {
                console.error("Không thể kết nối đến API backend " + API_URL);
                $('.price-buy, .price-sell').text("Bảo trì").css('color', 'red').css('font-size', '12px');
            }
        });
    }

    // --- Hàm cập nhật hiển thị tỷ giá (dưới form) ---
    function updateRateDisplay(rates) {
        let rate = 0;
        let text = '';
        const coinName = currentCoin === 'bustabit' ? 'BTC' : 'USDT';

        // Lấy đúng tỷ giá Mua hoặc Bán
        if (currentMode === 'buy') {
            rate = rates[currentCoin] ? rates[currentCoin].buy : 0;
        } else {
            rate = rates[currentCoin] ? rates[currentCoin].sell : 0;
        }

        text = `1 ${coinName} = ${numberFormat(rate, 0)} VNĐ`;
        $('#rate-display').text(text);
    }

    // --- Hàm gọi API tính toán (2 chiều) ---
    function calculateSwap(inputType, amountIn) {
        if (isCalculating) return;
        isCalculating = true;

        if (amountIn === 0) {
            $('#input-coin').val('0.00');
            $('#input-vnd').val('0.00');
            isCalculating = false;
            return;
        }

        let calculationDirection = 'from';
        if (currentMode === 'buy' && inputType === 'coin') {
            calculationDirection = 'to'; // Mua, gõ vào ô Coin (To)
        } else if (currentMode === 'buy' && inputType === 'vnd') {
            calculationDirection = 'from'; // Mua, gõ vào ô VNĐ (From)
        } else if (currentMode === 'sell' && inputType === 'coin') {
            calculationDirection = 'from'; // Bán, gõ vào ô Coin (From)
        } else if (currentMode === 'sell' && inputType === 'vnd') {
            calculationDirection = 'to'; // Bán, gõ vào ô VNĐ (To)
        }

        $.ajax({
            url: API_URL + "/api/calculate",
            type: 'POST',
            global: false,
            contentType: 'application/json',
            data: JSON.stringify({
                amount: amountIn,
                direction: calculationDirection,
                mode: currentMode,
                coin: currentCoin
            }),
            success: function (data) {
                if (inputType === 'coin') {
                    $('#input-vnd').val(numberFormat(data.amount_out, 0));
                } else {
                    $('#input-coin').val(numberFormat(data.amount_out, 8));
                }
                if (currentMode === 'buy' && inputType === 'coin') {
                    let threshold = data.threshold_info || 0;
                    let feeToShow = data.fee_applied || 0;

                    let currentRate = 0;
                    if (current_rates[currentCoin]) {
                        currentRate = current_rates[currentCoin].buy;
                    }

                    let baseRateText = `1 ${currentCoin.toUpperCase()} = ${numberFormat(currentRate, 0)} VNĐ`;

                    if (currentCoin === 'bustabit' && threshold > 0) {
                        if (amountIn > 0 && amountIn < threshold) {
                            $('#rate-display').html(`
                                ${baseRateText} <br>
                                <span style="color:#d9534f;">Phí giao dịch: ${numberFormat(feeToShow)} đ</span> <br> 
                                <small style="color:#28a745; font-weight:bold;">💡 Mua >= ${numberFormat(threshold)} Bits để được Miễn Phí!</small>
                            `);
                        } else if (amountIn >= threshold) {
                            $('#rate-display').html(`
                                ${baseRateText} <br>
                                <span style="color:#28a745; font-weight:bold;">🎉 Đã đạt ngưỡng miễn phí giao dịch!</span>
                            `);
                        } else {
                            $('#rate-display').text(baseRateText);
                        }
                    } else {
                        $('#rate-display').text(baseRateText);
                    }
                }
                isCalculating = false;
                validateLiquidity();
            },
            error: function () {
                console.error("Lỗi khi tính toán swap.");
                isCalculating = false;
            }
        });
    }

    // --- Hàm cập nhật giao diện Form (Khi đổi tab Mua/Bán) ---
    function updateFormUI() {
        if (currentMode === 'buy') {
            $('#label-coin').text('Bạn nhận (Coin)');
            $('#label-vnd').text('Bạn trả (VNĐ)');
            $('#btn-submit-swap').css('background-color', '#6cb55a');
        } else {
            $('#label-coin').text('Bạn gửi (Coin)');
            $('#label-vnd').text('Bạn nhận (VNĐ)');
            $('#btn-submit-swap').css('background-color', '#b94a48');
        }
        $('#buy-sell-tabs > li').removeClass('active');
        if (currentMode === 'buy') {
            $('#buy-sell-tabs a[href="#buy-tab"]').parent().addClass('active');
        } else {
            $('#buy-sell-tabs a[href="#sell-tab"]').parent().addClass('active');
        }

        $('#coin-balance').text('Số dư: 0.00 ' + currentCoin.toUpperCase());
        $('#input-coin').val('0.00');
        $('#input-vnd').val('0.00');
        updatePrices();
    }

    function validateInput(input) {
        let value = input.value.replace(/[^0-9.]/g, '');

        if ((value.match(/\./g) || []).length > 1) {
            value = value.replace(/\.+$/, "");
        }

        if (value !== input.value) {
            input.value = value;
        }
    }

    $('#input-coin, #input-vnd').on('input', function () {
        validateInput(this);
    });

    $('#input-coin, #input-vnd').on('paste', function (e) {
        let pastedData = e.originalEvent.clipboardData.getData('text');
        if (!/^[0-9.]+$/.test(pastedData)) {
            e.preventDefault();
            alert("Vui lòng chỉ dán số!");
        }
    });

    // --- KÍCH HOẠT CÁC SỰ KIỆN FORM SWAP ---
    $('#input-coin').on('keyup', function () {
        let amount = parseFloat($(this).val().replace(/,/g, '')) || 0;
        calculateSwap('coin', amount);
    });

    $('#input-vnd').on('keyup', function () {
        let amount = parseFloat($(this).val().replace(/,/g, '')) || 0;
        calculateSwap('vnd', amount);
    });

    $('#buy-sell-tabs a').on('click', function (e) {
        e.preventDefault();
        let newMode = $(this).attr('href') === '#buy-tab' ? 'buy' : 'sell';
        if (newMode !== currentMode) {
            currentMode = newMode;
            updateFormUI();
        }
    });

    function loadSiteConfig() {
        $.ajax({
            url: API_URL + "/api/site-config",
            type: 'GET',
            success: function (res) {
                if (res.success) {
                    // 1. Cập nhật bảng phí
                    if (res.fee_table) {
                        $('#fee-table-body').html(res.fee_table);
                    }
                    window.siteLiquidity = res.liquidity;
                    updateBalanceDisplay();
                }
            }
        });
    }
    // --- HÀM 1: CẬP NHẬT HIỂN THỊ TỶ GIÁ (Dưới nút Tiếp tục) ---
    function updateRateDisplay(rates) {
        let rate = 0;
        let coinName = 'USDT';

        if (currentCoin === 'bustabit' || currentCoin === 'btc') {
            coinName = 'Bits (BTC)';
        } else if (currentCoin === 'ether' || currentCoin === 'eth') {
            coinName = 'Ethos (ETH)';
        } else if (currentCoin === 'bnb') {
            coinName = 'BNB - BEP20';
        } else if (currentCoin === 'sol') {
            coinName = 'SOLANA - SOL';
        } else {
            coinName = 'USDT - BEP20';
        }

        if (rates[currentCoin]) {
            if (currentMode === 'buy') {
                rate = rates[currentCoin].buy;
            } else {
                rate = rates[currentCoin].sell;
            }
        } else {
            rate = 0;
        }

        let text = `Với giá: 1 ${coinName} = ${numberFormat(rate, 0)} VNĐ`;
        $('#rate-display').text(text);
    }

    // --- HÀM 2: CẬP NHẬT HIỂN THỊ SỐ DƯ (Chữ nhỏ trong ô nhập) ---
    function updateBalanceDisplay() {
        if (!window.siteLiquidity) return;

        $('#input-vnd').closest('.swap-field').find('.balance-info').text('');

        let coinBal = 0;
        let unit = currentCoin.toUpperCase();

        if (currentCoin === 'bustabit' || currentCoin === 'btc') {
            coinBal = window.siteLiquidity.btc;
            unit = 'Bits';
        } else if (currentCoin === 'usdt') {
            coinBal = window.siteLiquidity.usdt;
        } else if (currentCoin === 'ether' || currentCoin === 'eth') {
            coinBal = window.siteLiquidity.eth;
            unit = 'Ethos';
        } else if (currentCoin === 'sol' || currentCoin === 'sol') {
            coinBal = window.siteLiquidity.sol;
            unit = 'SOL';
        } else if (currentCoin === 'bnb' || currentCoin === 'bnb') {
            coinBal = window.siteLiquidity.eth;
            unit = 'BNB (BEP20)';
        } else {
            coinBal = 0;
        }

        $('#input-coin').closest('.swap-field').find('.balance-info').text(`Số dư hệ thống: ${numberFormat(coinBal, 2)} ${unit}`);
    }

    loadSiteConfig();

    $('#coin-list a').on('click', function (e) {
        e.preventDefault();
        let coinText = $(this).text();
        let coinIcon = $(this).data('icon');
        currentCoin = $(this).data('coin');

        // Cập nhật dropdown
        $('#coin-text').text(coinText);
        $('#coin-icon').attr('src', coinIcon);

        $('#coin-balance').text('Số dư: 0 ' + currentCoin.toUpperCase());

        updatePrices();
        // Tính toán lại dựa trên ô VNĐ (vì ô Coin bị reset)
        calculateSwap('vnd', parseFloat($('#input-vnd').val().replace(/,/g, '')) || 0);
        updateBalanceDisplay();
    });

    // --- QUẢN LÝ PHIÊN ĐĂNG NHẬP (UI) ---
    function checkLoginState() {
        const userDataString = localStorage.getItem('buser_user');
        if (userDataString) {
            const user = JSON.parse(userDataString);
            $('#menu-register').hide();
            $('#menu-login').hide();
            $('#menu-profile').show();
            $('#menu-logout').show();
            if (user.role === 'Admin') {
                $('#menu-admin').show();
            }
            $('#btn-submit-swap').text('Tiếp tục').removeClass('btn-primary').addClass('btn-success');
            if ($('#sidebar-username').length > 0) {
                $('#sidebar-username').text(user.username);
            }
        } else {
            $('#menu-register').show();
            $('#menu-login').show();
            $('#menu-profile').hide();
            $('#menu-admin').hide();
            $('#menu-logout').hide();
            $('#btn-submit-swap').text('Đăng Nhập / Đăng Ký').removeClass('btn-success').addClass('btn-primary');
        }
    }

    // --- [CẬP NHẬT] Hàm tải Lịch sử Giao dịch Công khai ---
    function loadPublicHistory() {
        $.ajax({
            url: API_URL + "/api/public-transactions",
            type: 'GET',
            success: function (response) {
                const historyTableBody = $('#history-table-body');
                if (response.success && response.transactions.length > 0) {
                    historyTableBody.empty();
                    response.transactions.forEach(tx => {
                        const timeOnly = tx.created_at.split(' ')[1] || tx.created_at;
                        const amountFormatted = numberFormat(tx.amount_coin, 2);

                        // [MỚI] Logic Icon và Màu sắc
                        let typeHtml = '';
                        if (tx.mode === 'Mua' || tx.mode === 'buy') {
                            // Mũi tên xuống màu xanh
                            typeHtml = `<span class="tx-buy"><i class="fa fa-arrow-down"></i> Mua</span>`;
                        } else {
                            // Mũi tên lên màu đỏ
                            typeHtml = `<span class="tx-sell"><i class="fa fa-arrow-up"></i> Bán</span>`;
                        }

                        const row = `
                        <tr>
                            <td>${typeHtml}</td>
                            <td style="font-weight:600; color:#333;">${escapeHTML(tx.coin)}</td>
                            <td class="text-right" style="font-family:monospace; font-size:13px;">${amountFormatted}</td>
                            <td class="text-right text-muted" style="font-size:12px;">${escapeHTML(timeOnly)}</td>
                        </tr>`;
                        historyTableBody.append(row);
                    });
                } else {
                    historyTableBody.html('<tr><td colspan="4" class="text-center" style="padding:20px;">Chưa có giao dịch nào.</td></tr>');
                }
            },
            error: function () {
                $('#history-table-body').html('<tr><td colspan="4" class="text-center text-danger">Lỗi tải dữ liệu.</td></tr>');
            }
        });
    }

    // --- [MỚI] Hàm tải Lịch sử Giao dịch CÁ NHÂN ---
    function loadPersonalHistory() {
        if (!localStorage.getItem('buser_user')) return;

        $.ajax({
            url: API_URL + "/api/user/my-transactions",
            type: 'GET',
            success: function (response) {
                const historyBody = $('#personal-history-body');
                if (response.success && response.transactions.length > 0) {
                    historyBody.empty();
                    response.transactions.forEach(tx => {
                        const amountCoin = numberFormat(tx.amount_coin, 8);
                        const amountVND = numberFormat(tx.amount_vnd, 0);
                        let statusClass = 'label-success';
                        if (tx.status_vi.includes('Đang chờ')) {
                            statusClass = 'label-warning';
                        } else if (tx.status_vi.includes('Đã hủy')) {
                            statusClass = 'label-danger';
                        }

                        let linkPage = tx.mode === 'Mua' ? 'checkout_payment_buy.html' : 'checkout_payment_sell.html';
                        if (tx.mode === 'buy' || tx.mode === 'Buy') linkPage = 'checkout_payment_buy.html';
                        if (tx.mode === 'sell' || tx.mode === 'Sell') linkPage = 'checkout_payment_sell.html';
                        if (tx.mode === 'Bán') linkPage = 'checkout_payment_sell.html';

                        const idLink = `<a href="${linkPage}?id=${escapeHTML(tx.id)}" style="font-weight:bold; text-decoration:underline;">${escapeHTML(tx.id)}</a>`;

                        const row = `
                        <tr>
                            <td>${idLink}</td> <td>${escapeHTML(tx.created_at)}</td>
                            <td>${escapeHTML(tx.mode)}</td>
                            <td>${escapeHTML(tx.coin)}</td>
                            <td>${amountCoin}</td>
                            <td>${amountVND} VNĐ</td>
                            <td><span class="label ${statusClass}">${tx.status_vi}</span></td>
                        </tr>`;
                        historyBody.append(row);
                    });
                } else {
                    historyBody.html('<tr><td colspan="6" class="text-center">Bạn chưa có giao dịch nào.</td></tr>');
                }
            },
            error: function (xhr) {
                $('#personal-history-body').html(`<tr><td colspan="6" class="text-center">Lỗi khi tải lịch sử: ${xhr.responseJSON ? xhr.responseJSON.message : "Lỗi kết nối"}</td></tr>`);
            }
        });
    }

    // --- Hàm tải danh sách VÍ (Wallet) đã lưu ---
    function loadWalletsList() {
        if (!localStorage.getItem('buser_user')) return;

        const tableBody = $('#wallets-table-body');
        const coins = ['bustabit', 'usdt', 'ether', 'bnb', 'sol'];

        // Tạo mảng các request Ajax
        let requests = coins.map(coin => {
            return $.ajax({
                url: `${API_URL}/api/user/wallets?coin_type=${coin}`,
                type: 'GET'
            });
        });

        // Hiển thị đang tải
        tableBody.html('<tr><td colspan="4" class="text-center"><i class="fa fa-spinner fa-spin"></i> Đang tải dữ liệu...</td></tr>');

        // Dùng $.when.apply để xử lý mảng request động (Tương thích tốt với jQuery 1.x)
        $.when.apply($, requests).done(function () {
            tableBody.empty();
            let allWallets = [];

            // Xử lý kết quả trả về (Lưu ý: $.when trả về các arguments khác nhau tùy số lượng request)
            // Nếu chỉ có 1 request, arguments là (data, status, xhr)
            // Nếu nhiều request, arguments là ([data, status, xhr], [data, status, xhr], ...)
            if (coins.length === 1) {
                if (arguments[0].wallets) allWallets = allWallets.concat(arguments[0].wallets);
            } else {
                for (let i = 0; i < arguments.length; i++) {
                    // arguments[i][0] là body response (data)
                    let res = arguments[i][0];
                    if (res && res.wallets) {
                        allWallets = allWallets.concat(res.wallets);
                    }
                }
            }

            if (allWallets.length === 0) {
                tableBody.html('<tr><td colspan="4" class="text-center">Bạn chưa lưu ví nào.</td></tr>');
                return;
            }

            allWallets.forEach(wallet => {
                let type = escapeHTML(wallet.coin_type.toUpperCase());

                // Xử lý hiển thị riêng cho từng loại Coin
                let mainInfoLabel = "Địa chỉ";
                let mainInfoValue = escapeHTML(wallet.address);
                let details = "";

                if (wallet.coin_type === 'ether') {
                    // Với Ether: Address trong DB chính là ID
                    mainInfoLabel = "Ethos ID";
                    // Thông tin phụ: Tên, SĐT
                    details = `<b>Tên:</b> ${escapeHTML(wallet.name)}<br><b>SĐT:</b> ${escapeHTML(wallet.phone)}`;
                }
                else if (wallet.coin_type === 'bustabit') {
                    // Với Bustabit: Cần hiện Tag
                    mainInfoLabel = "Địa chỉ";
                    let tagShow = (wallet.tag && wallet.tag !== 'null') ? wallet.tag : 'N/A';
                    details = `<b>Tag:</b> ${escapeHTML(tagShow)}<br><b>Tên:</b> ${escapeHTML(wallet.name)}<br><b>SĐT:</b> ${escapeHTML(wallet.phone)}`;
                }
                else {
                    // Với USDT, BNB, SOL: Chỉ hiện Tên, SĐT
                    mainInfoLabel = "Địa chỉ";
                    details = `<b>Tên:</b> ${escapeHTML(wallet.name)}<br><b>SĐT:</b> ${escapeHTML(wallet.phone)}`;
                }

                const row = `
                <tr id="wallet-row-${escapeHTML(wallet.id)}">
                    <td><span class="label label-primary">${type}</span></td>
                    <td>
                        <small class="text-muted">${mainInfoLabel}:</small><br>
                        <strong>${mainInfoValue}</strong>
                    </td>
                    <td><small>${details}</small></td>
                    <td>
                        <button class="btn btn-xs btn-danger btn-delete-wallet" data-id="${escapeHTML(wallet.id)}">
                            <i class="fa fa-trash"></i> Xóa
                        </button>
                    </td>
                </tr>`;
                tableBody.append(row);
            });

        }).fail(function () {
            tableBody.html('<tr><td colspan="4" class="text-center text-danger">Lỗi khi tải dữ liệu ví. Vui lòng thử lại.</td></tr>');
        });
    }

    // --- [MỚI] Hàm tải danh sách NGÂN HÀNG (Bank) đã lưu ---
    function loadBanksList() {
        if (!localStorage.getItem('buser_user')) return;
        const tableBody = $('#banks-table-body');

        $.ajax({
            url: `${API_URL}/api/user/banks`,
            type: 'GET',
            success: function (response) {
                tableBody.empty(); // Xóa "Đang tải..."
                if (response.success && response.banks.length > 0) {
                    response.banks.forEach(bank => {
                        const row = `
                        <tr id="bank-row-${escapeHTML(bank.id)}">
                        <td>${escapeHTML(bank.bank_name)}</td>
                        <td>${escapeHTML(bank.account_number)}</td>
                        <td>${escapeHTML(bank.account_name)}</td>
                        <td><button class="btn btn-xs btn-danger btn-delete-bank" data-id="${escapeHTML(bank.id)}"><i class="fa fa-trash"></i> Xóa</button></td>
                        </tr>`;
                        tableBody.append(row);
                    });
                } else {
                    tableBody.html('<tr><td colspan="4" class="text-center">Bạn chưa lưu ngân hàng nào.</td></tr>');
                }
            },
            error: function () {
                tableBody.html('<tr><td colspan="4" class="text-center">Lỗi khi tải danh sách ngân hàng.</td></tr>');
            }
        });
    }

    // --- [MỚI] Xử lý sự kiện XÓA VÍ ---
    // Dùng $(document).on(...) vì các nút này được tạo động
    $(document).on('click', '.btn-delete-wallet', function () {
        const walletId = $(this).data('id');
        if (!confirm('Bạn có chắc chắn muốn xóa ví này không?')) {
            return;
        }

        $.ajax({
            url: `${API_URL}/api/user/delete-wallet`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ wallet_id: walletId }),
            success: function (response) {
                alert(response.message);
                $(`#wallet-row-${walletId}`).fadeOut(500, function () { $(this).remove(); });
            },
            error: function (xhr) {
                alert('Lỗi: ' + xhr.responseJSON.message);
            }
        });
    });

    // --- [MỚI] Xử lý sự kiện XÓA NGÂN HÀNG ---
    $(document).on('click', '.btn-delete-bank', function () {
        const bankId = $(this).data('id');
        if (!confirm('Bạn có chắc chắn muốn xóa ngân hàng này không?')) {
            return;
        }

        $.ajax({
            url: `${API_URL}/api/user/delete-bank`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ bank_id: bankId }),
            success: function (response) {
                alert(response.message);
                $(`#bank-row-${bankId}`).fadeOut(500, function () { $(this).remove(); });
            },
            error: function (xhr) {
                alert('Lỗi: ' + xhr.responseJSON.message);
            }
        });
    });

    $('#btn-logout').on('click', function (e) {
        e.preventDefault();

        if (!confirm("Bạn có chắc muốn đăng xuất?")) {
            return;
        }

        localStorage.removeItem('buser_user');
        alert("Đăng xuất thành công!");
        window.location.href = "index.html";
    });

    function isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    // --- XỬ LÝ FORM ĐĂNG KÝ ---
    $("#register-form").on('submit', function (e) {
        e.preventDefault();
        const email = $(this).find('input[name="email"]').val();
        if (!isValidEmail(email)) {
            alert("Email không hợp lệ!");
            return;
        }
        var data = {
            username: $(this).find('input[name="username"]').val(),
            email: $(this).find('input[name="email"]').val(),
            password: $(this).find('input[name="password"]').val()
        };
        $.ajax({
            url: API_URL + "/api/register",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function (response) {
                alert(response.message);
                window.location.href = "login.html";
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
            }
        });
    });

    // --- XỬ LÝ FORM ĐĂNG NHẬP ---
    $("#login-form").on('submit', function (e) {
        e.preventDefault();
        var data = {
            username: $(this).find('input[name="username"]').val(),
            password: $(this).find('input[name="password"]').val()
        };
        $.ajax({
            url: API_URL + "/api/login",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function (response) {
                alert(response.message);
                localStorage.setItem('buser_user', JSON.stringify(response.user));
                window.location.href = "index.html";
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
            }
        });
    });

    // --- XỬ LÝ NÚT "TIẾP TỤC" (LƯU LỰA CHỌN) ---
    $('#btn-submit-swap').on('click', function () {
        if (!localStorage.getItem('buser_user')) return;

        // [SỬA LỖI] Đọc từ các ID input mới
        let amountCoin = parseFloat($('#input-coin').val().replace(/,/g, '')) || 0;
        let amountVND = parseFloat($('#input-vnd').val().replace(/,/g, '')) || 0;

        if (amountCoin === 0 || amountVND === 0) {
            alert("Vui lòng nhập số lượng hợp lệ.");
            return;
        }

        // [SỬA LỖI] Logic mới để gán amount_from và amount_to
        let amount_from = 0;
        let amount_to = 0;

        if (currentMode === 'buy') {
            // MUA: From = VNĐ, To = Coin
            amount_from = amountVND;
            amount_to = amountCoin;
        } else {
            // BÁN: From = Coin, To = VNĐ
            amount_from = amountCoin;
            amount_to = amountVND;
        }

        // 1. [MỚI] Chỉ lưu lựa chọn vào localStorage (chưa tạo đơn hàng)
        var draftOrder = {
            mode: currentMode,
            coin: currentCoin,
            amount_from: amount_from,
            amount_to: amount_to
        };
        localStorage.setItem('draft_order', JSON.stringify(draftOrder));

        // 2. Chuyển hướng đến trang CHỌN LỰA
        if (currentMode === 'buy') {
            window.location.href = "checkout_select_wallet.html";
        } else {
            window.location.href = "checkout_select_bank.html";
        }
    });

    // --- XỬ LÝ TRANG HỒ SƠ ---
    if ($('#change-pass-form').length > 0) {
        const userDataString = localStorage.getItem('buser_user');
        if (userDataString) {
            const user = JSON.parse(userDataString);
            $('#profile-email').val(user.email);
        } else {
            window.location.href = "login.html";
        }

        let historyLoaded = false; // Cờ để chỉ tải 1 lần
        $('a[data-toggle="tab"][href="#history"]').on('shown.bs.tab', function (e) {
            if (!historyLoaded) {
                loadPersonalHistory();
                historyLoaded = true;
            }
        });
        let walletsLoaded = false;
        $('a[data-toggle="tab"][href="#wallets"]').on('shown.bs.tab', function (e) {
            if (!walletsLoaded) {
                loadWalletsList();
                walletsLoaded = true; // Chỉ tải 1 lần, nếu muốn tải lại thì xóa dòng này
            }
        });

        // [MỚI] Kích hoạt tải NGÂN HÀNG khi nhấn tab
        let banksLoaded = false;
        $('a[data-toggle="tab"][href="#banks"]').on('shown.bs.tab', function (e) {
            if (!banksLoaded) {
                loadBanksList();
                banksLoaded = true; // Chỉ tải 1 lần
            }
        });
    }

    $('#change-pass-form').on('submit', function (e) {
        e.preventDefault();
        let newPass = $(this).find('input[name="new_password"]').val();
        let confirmPass = $(this).find('input[name="confirm_password"]').val();
        if (newPass !== confirmPass) {
            alert("Lỗi: Mật khẩu mới không khớp!");
            return;
        }
        var data = {
            old_password: $(this).find('input[name="old_password"]').val(),
            new_password: newPass
        };
        $.ajax({
            url: API_URL + "/api/change-password",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function (response) {
                alert(response.message);
                $('#change-pass-form')[0].reset();
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
            }
        });
    });

    $('#change-email-form').on('submit', function (e) {
        e.preventDefault();
        var data = {
            new_email: $(this).find('input[name="new_email"]').val()
        };
        $.ajax({
            url: API_URL + "/api/change-email",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function (response) {
                alert(response.message);
                // Cập nhật email trong localStorage
                const userDataString = localStorage.getItem('buser_user');
                if (userDataString) {
                    let user = JSON.parse(userDataString);
                    user.email = data.new_email;
                    localStorage.setItem('buser_user', JSON.stringify(user));
                }
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
            }
        });
    });

    // --- XỬ LÝ QUÊN MẬT KHẨU (FORGOT-PASSWORD.HTML) ---
    $('#forgot-password-form').on('submit', function (e) {
        e.preventDefault();
        var data = { email: $(this).find('input[type="email"]').val() };
        $.ajax({
            url: API_URL + "/api/forgot-password",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function (response) { alert(response.message); },
            error: function (xhr) { alert("Lỗi: " + xhr.responseJSON.message); }
        });
    });


    // --- XỬ LÝ TRANG ADMIN SETTINGS ---
    var adminBanks = [];
    var supportedBanks = [];

    if ($('#settings-form').length > 0) {
        $.ajax({
            url: API_URL + "/api/admin/settings",
            type: 'GET',
            success: function (response) {
                if (response.success) {
                    $('select[name="maintenance_mode"]').val(response.settings.maintenance_mode || 'off');
                    $('input[name="admin_bustabit_id"]').val(response.settings.admin_bustabit_id);
                    $('input[name="admin_usdt_wallet"]').val(response.settings.admin_usdt_wallet);
                    $('input[name="admin_ether_id"]').val(response.settings.admin_ether_id || '');
                    $('input[name="admin_bnb_wallet"]').val(response.settings.admin_bnb_wallet || '');
                    $('input[name="admin_sol_wallet"]').val(response.settings.admin_sol_wallet || '');
                    $('input[name="telegram_bot_token"]').val(response.settings.TELEGRAM_BOT_TOKEN || '');
                    $('input[name="telegram_chat_id"]').val(response.settings.TELEGRAM_CHAT_ID || '');
                    $('input[name="liquidity_vnd"]').val(response.settings.liquidity_vnd);
                    $('input[name="liquidity_usdt"]').val(response.settings.liquidity_usdt);
                    $('input[name="liquidity_btc"]').val(response.settings.liquidity_btc);
                    $('input[name="liquidity_eth"]').val(response.settings.liquidity_eth);
                    $('input[name="liquidity_bnb"]').val(response.settings.liquidity_bnb);
                    $('input[name="liquidity_sol"]').val(response.settings.liquidity_sol);
                    if (response.settings.coin_fees) {
                        const fees = response.settings.coin_fees;

                        const getFee = (coin) => (fees[coin] && typeof fees[coin] === 'object') ? fees[coin].fee : (fees[coin] || 0);
                        const getThresh = (coin) => (fees[coin] && typeof fees[coin] === 'object') ? fees[coin].threshold : 0;

                        $('input[name="fee_bustabit_amount"]').val(getFee('bustabit'));
                        $('input[name="fee_bustabit_threshold"]').val(getThresh('bustabit'));

                        $('input[name="fee_ether_amount"]').val(getFee('ether'));
                        $('input[name="fee_ether_threshold"]').val(getThresh('ether'));

                        $('input[name="fee_usdt_amount"]').val(getFee('usdt'));
                        $('input[name="fee_usdt_threshold"]').val(getThresh('usdt'));

                        $('input[name="fee_sol_amount"]').val(getFee('sol'));
                        $('input[name="fee_sol_threshold"]').val(getThresh('sol'));

                        $('input[name="fee_bnb_amount"]').val(getFee('bnb'));
                        $('input[name="fee_bnb_threshold"]').val(getThresh('bnb'));
                    }
                    $('textarea[name="fee_html_content"]').val(response.settings.fee_html_content);

                    if (response.settings.admin_banks && Array.isArray(response.settings.admin_banks) && response.settings.admin_banks.length > 0) {
                        adminBanks = response.settings.admin_banks;
                    } else {
                        // Nếu chưa có mảng bank, thử fallback về dữ liệu cũ hoặc tạo mảng rỗng
                        if (response.settings.admin_bank_bin) {
                            adminBanks = [{
                                bank_name: "Ngân hàng mặc định",
                                bin: response.settings.admin_bank_bin || "",
                                acc: response.settings.admin_account_number || "",
                                name: response.settings.admin_account_name || ""
                            }];
                        } else {
                            adminBanks = [];
                        }
                    }
                    renderBankTable();

                    supportedBanks = response.settings.supported_banks || [];
                    renderSupportedBanks();
                }
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
                window.location.href = "index.html";
            }
        });
    }

    function renderSupportedBanks() {
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
    }

    window.updateSupBank = function (index, field, value) { supportedBanks[index][field] = value; }
    window.removeSupBank = function (index) { supportedBanks.splice(index, 1); renderSupportedBanks(); }
    $('#btn-add-supported-bank').click(function () {
        supportedBanks.push({ name: "", short_name: "", bin: "" });
        renderSupportedBanks();
    });

    function renderBankTable() {
        const tbody = $('#bank-list-table tbody');
        tbody.empty();

        if (adminBanks.length === 0) {
            tbody.append('<tr><td colspan="5" class="text-center">Chưa có ngân hàng nào. Hãy thêm mới.</td></tr>');
            return;
        }

        adminBanks.forEach((bank, index) => {
            const row = `
                <tr>
                    <td><input type="text" class="form-control input-sm" value="${escapeHTML(bank.bank_name)}" onchange="updateBank(${index}, 'bank_name', this.value)" placeholder="VD: Vietcombank"></td>
                    <td><input type="text" class="form-control input-sm" value="${escapeHTML(bank.bin)}" onchange="updateBank(${index}, 'bin', this.value)" placeholder="970436"></td>
                    <td><input type="text" class="form-control input-sm" value="${escapeHTML(bank.acc)}" onchange="updateBank(${index}, 'acc', this.value)"></td>
                    <td><input type="text" class="form-control input-sm" value="${escapeHTML(bank.name)}" onchange="updateBank(${index}, 'name', this.value)"></td>
                    <td><button type="button" class="btn btn-danger btn-xs" onclick="removeBank(${index})"><i class="fa fa-trash"></i></button></td>
                </tr>
            `;
            tbody.append(row);
        });
    }

    // Gán hàm vào window để gọi được từ onclick trong HTML
    window.updateBank = function (index, field, value) {
        if (adminBanks[index]) {
            adminBanks[index][field] = value;
        }
    }
    window.removeBank = function (index) {
        adminBanks.splice(index, 1);
        renderBankTable();
    }

    // Xử lý nút Thêm Ngân hàng
    $('#btn-add-bank').off('click').on('click', function () {
        adminBanks.push({ bank_name: "", bin: "", acc: "", name: "" });
        renderBankTable();
    });

    $('#settings-form').on('submit', function (e) {
        e.preventDefault();
        const cleanBanks = adminBanks.filter(b => b.bin && b.acc);

        var settingsData = {
            maintenance_mode: $('select[name="maintenance_mode"]').val(),
            admin_bustabit_id: $('input[name="admin_bustabit_id"]').val(),
            admin_usdt_wallet: $('input[name="admin_usdt_wallet"]').val(),
            admin_ether_id: $('input[name="admin_ether_id"]').val(),
            admin_bnb_wallet: $('input[name="admin_bnb_wallet"]').val(),
            admin_sol_wallet: $('input[name="admin_sol_wallet"]').val(),
            TELEGRAM_BOT_TOKEN: $('input[name="telegram_bot_token"]').val(),
            TELEGRAM_CHAT_ID: $('input[name="telegram_chat_id"]').val(),
            liquidity_vnd: $('input[name="liquidity_vnd"]').val(),
            liquidity_usdt: $('input[name="liquidity_usdt"]').val(),
            liquidity_btc: $('input[name="liquidity_btc"]').val(),
            liquidity_eth: $('input[name="liquidity_eth"]').val(),
            liquidity_bnb: $('input[name="liquidity_bnb"]').val(),
            liquidity_sol: $('input[name="liquidity_sol"]').val(),
            coin_fees: {
                bustabit: {
                    fee: $('input[name="fee_bustabit_amount"]').val(),
                    threshold: $('input[name="fee_bustabit_threshold"]').val()
                },
                ether: {
                    fee: $('input[name="fee_ether_amount"]').val(),
                    threshold: $('input[name="fee_ether_threshold"]').val()
                },
                usdt: {
                    fee: $('input[name="fee_usdt_amount"]').val(),
                    threshold: $('input[name="fee_usdt_threshold"]').val()
                },
                sol: {
                    fee: $('input[name="fee_sol_amount"]').val(),
                    threshold: $('input[name="fee_sol_threshold"]').val()
                },
                bnb: {
                    fee: $('input[name="fee_bnb_amount"]').val(),
                    threshold: $('input[name="fee_bnb_threshold"]').val()
                }
            },
            fee_html_content: $('textarea[name="fee_html_content"]').val(),
            admin_banks: cleanBanks
        };

        settingsData.supported_banks = supportedBanks;

        $.ajax({
            url: API_URL + "/api/admin/settings",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(settingsData),
            success: function (response) { alert(response.message); location.reload(); },
            error: function (xhr) { alert("Lỗi: " + xhr.responseJSON.message); }
        });
    });

    // --- KHỞI CHẠY ---
    checkLoginState();
    if ($('#swap-form-panel').length > 0) { // Chỉ chạy nếu ở trang chủ
        updatePrices();
        setInterval(updatePrices, 15000);
        updateFormUI();
        loadPublicHistory();
    }

    // --- XỬ LÝ GIAO DIỆN THÊM VÍ (add-wallet.html) ---
    if ($('#add-wallet-form').length > 0) {
        function toggleWalletFields() {
            const type = $('#coin-type-select').val();


            // 1. Mặc định: Hiện Địa chỉ, Ẩn Tag
            $('#field-address-group').show();
            $('#field-tag-group').hide();

            // [SỬA ĐỔI QUAN TRỌNG] Luôn hiện nhóm thông tin cá nhân cho TẤT CẢ các coin
            $('#field-personal-group').show();

            if (type === 'bustabit') {
                // Bustabit: Cần thêm Tag
                $('#field-tag-group').show();
                $('#label-tag').text('Destination Tag:');
            }
            else if (type === 'ether') {
                // Ether: ẨN địa chỉ ví, Hiện Tag (làm ID)
                $('#field-address-group').hide();
                $('#field-tag-group').show();
                $('#label-tag').text('Ethos ID (Destination Tag):');
            }
            else {
                // USDT, BNB, SOL: Chỉ cần Địa chỉ ví (Tag vẫn ẩn)
                // Họ tên & SĐT đã được hiện ở dòng mặc định bên trên
            }
            if (type === 'bustabit' || type === 'bnb' || type === 'sol') {
                $('#field-tag-group').show();
                $('#label-tag').text(type === 'bustabit' ? 'Destination Tag:' : 'Memo (Nếu có):');
            }
        }

        // Chạy lần đầu và khi thay đổi
        toggleWalletFields();
        $('#coin-type-select').on('change', toggleWalletFields);
    }

    // --- XỬ LÝ FORM THÊM VÍ (add-wallet.html) ---
    $('#add-wallet-form').on('submit', function (e) {
        e.preventDefault();

        var coinType = $(this).find('select[name="coin_type"]').val();
        var inputAddress = $(this).find('input[name="address"]').val();
        var inputTag = $(this).find('input[name="tag"]').val();

        // [QUAN TRỌNG] Luôn lấy thông tin Họ tên & SĐT cho mọi loại coin
        var inputName = $(this).find('input[name="name"]').val();
        var inputPhone = $(this).find('input[name="phone"]').val();

        // Logic xử lý dữ liệu riêng cho từng coin
        if (coinType === 'ether') {
            if (!inputTag) {
                alert("Vui lòng nhập Ethos ID (Tag)!");
                return;
            }
            // Ether dùng Tag làm Address
            inputAddress = inputTag;
        }
        else if (coinType === 'bustabit') {
            if (!inputAddress) { alert("Vui lòng nhập địa chỉ!"); return; }
        }
        else {
            if (!inputAddress) { alert("Vui lòng nhập địa chỉ ví!"); return; }
        }

        // Kiểm tra bắt buộc nhập tên và sđt (nếu bạn muốn bắt buộc)
        if (!inputName || !inputPhone) {
            alert("Vui lòng nhập đầy đủ Họ tên và Số điện thoại!");
            return;
        }

        var data = {
            coin_type: coinType,
            address: inputAddress,
            tag: inputTag,
            name: inputName,
            phone: inputPhone
        };

        $.ajax({
            url: API_URL + "/api/user/add-wallet",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function (response) {
                alert(response.message);
                if (document.referrer && document.referrer.includes('profile.html')) {
                    window.location.href = "profile.html#wallets";
                } else {
                    window.location.href = "checkout_select_wallet.html";
                }
            },
            error: function (xhr) {
                alert("Lỗi: " + (xhr.responseJSON ? xhr.responseJSON.message : "Lỗi không xác định"));
            }
        });
    });

    // --- XỬ LÝ FORM THÊM NGÂN HÀNG (add-bank.html) ---
    $('#add-bank-form').on('submit', function (e) {
        e.preventDefault();

        var data = {
            bank_name: $(this).find('select[name="bank_name"]').val(),
            account_number: $(this).find('input[name="account_number"]').val(),
            account_name: $(this).find('input[name="account_name"]').val()
        };

        $.ajax({
            url: API_URL + "/api/user/add-bank",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function (response) {
                alert(response.message);
                if (document.referrer && document.referrer.includes('profile.html')) {
                    window.location.href = "profile.html#banks";
                } else {
                    window.location.href = "checkout_select_bank.html";
                }
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
            }
        });
    });

    // --- HÀM KIỂM TRA GIỚI HẠN MUA ---
    function validateLiquidity() {
        if (currentMode !== 'buy') {
            $('#btn-submit-swap').prop('disabled', false).text('Tiếp tục');
            $('#input-coin').css('border-color', '#ccc');
            $('#liquidity-warning').remove();
            return true;
        }

        if (!window.siteLiquidity) return true;

        let amountCoin = parseFloat($('#input-coin').val().replace(/,/g, '')) || 0;
        let limit = 0;

        if (currentCoin === 'bustabit' || currentCoin === 'btc') limit = window.siteLiquidity.btc;
        else if (currentCoin === 'usdt') limit = window.siteLiquidity.usdt;
        else if (currentCoin === 'ether' || currentCoin === 'eth') limit = window.siteLiquidity.eth;
        else if (currentCoin === 'bnb') limit = window.siteLiquidity.bnb;
        else if (currentCoin === 'sol') limit = window.siteLiquidity.sol;
        else limit = 1000000; // Các coin chưa config thì không giới hạn

        if (amountCoin > limit) {
            $('#btn-submit-swap').prop('disabled', true).text('Vượt quá số dư hệ thống');
            $('#input-coin').css('border-color', 'red');

            if ($('#liquidity-warning').length === 0) {
                $('#input-coin').parent().after('<div id="liquidity-warning" style="color:red; font-size:12px; margin-top:5px;">Xin lỗi, hệ thống chỉ còn ' + numberFormat(limit, 2) + ' ' + currentCoin.toUpperCase() + '</div>');
            } else {
                $('#liquidity-warning').text('Xin lỗi, hệ thống chỉ còn ' + numberFormat(limit, 2) + ' ' + currentCoin.toUpperCase());
            }
            return false;
        } else {
            $('#btn-submit-swap').prop('disabled', false).text('Tiếp tục');
            $('#input-coin').css('border-color', '#ccc');
            $('#liquidity-warning').remove();
            return true;
        }
    }
    function copyToClipboard(elementId) {
        var $temp = $("<input>");
        $("body").append($temp);
        $temp.val($(elementId).text()).select();
        document.execCommand("copy");
        $temp.remove();
        // Hiệu ứng thông báo nhỏ (Optional)
        alert("Đã sao chép: " + $(elementId).text());
    }
});
