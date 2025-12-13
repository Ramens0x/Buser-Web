$(document).ready(function () {
    // Chỉ chạy code này nếu đang ở trang chủ (có khung Swap)
    if ($('#swap-form-panel').length === 0) {
        return;
    }

    let currentMode = 'buy';
    let currentCoin = 'bustabit';
    let isCalculating = false;
    let current_rates = {}; // Biến lưu tỷ giá cục bộ

    // --- 1. HÀM CẬP NHẬT GIÁ ---
    function updatePrices() {
        $.ajax({
            url: API_URL + "/api/prices",
            type: 'GET',
            global: false, // Không hiện loading khi update ngầm
            success: function (data) {
                current_rates = data;

                const showPrice = (price) => {
                    return (price && price > 0) ? numberFormat(price, 0) + ' ₫' : '<span style="font-size:12px; color:#999;">Đang cập nhật</span>';
                };

                // Cập nhật giá trên bảng bên phải
                if (data.bustabit) { $('#bustabit-buy').html(showPrice(data.bustabit.buy)); $('#bustabit-sell').html(showPrice(data.bustabit.sell)); }
                if (data.ether) { $('#ether-buy').html(showPrice(data.ether.buy)); $('#ether-sell').html(showPrice(data.ether.sell)); }
                if (data.btc) { $('#btc-buy').html(showPrice(data.btc.buy)); $('#btc-sell').html(showPrice(data.btc.sell)); }
                if (data.usdt) { $('#usdt-buy').html(showPrice(data.usdt.buy)); $('#usdt-sell').html(showPrice(data.usdt.sell)); }
                if (data.usdc) { $('#usdc-buy').html(showPrice(data.usdc.buy)); $('#usdc-sell').html(showPrice(data.usdc.sell)); }
                if (data.eth) { $('#eth-buy').html(showPrice(data.eth.buy)); $('#eth-sell').html(showPrice(data.eth.sell)); }
                if (data.bnb) { $('#bnb-buy').html(showPrice(data.bnb.buy)); $('#bnb-sell').html(showPrice(data.bnb.sell)); }
                if (data.sol) { $('#sol-buy').html(showPrice(data.sol.buy)); $('#sol-sell').html(showPrice(data.sol.sell)); }
                if (data.itlg) { $('#itlg-buy').html(showPrice(data.itlg.buy)); $('#itlg-sell').html(showPrice(data.itlg.sell)); }
                if (data.itl) { $('#itl-buy').html(showPrice(data.itl.buy)); $('#itl-sell').html(showPrice(data.itl.sell)); }

                updateRateDisplay(data);
            },
            error: function () {
                console.error("Không thể kết nối đến API giá.");
                $('.price-buy, .price-sell').text("Bảo trì").css('color', 'red').css('font-size', '12px');
            }
        });
    }

    // --- 2. HÀM TÍNH TOÁN SWAP ---
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
        if (currentMode === 'buy') {
            calculationDirection = (inputType === 'coin') ? 'to' : 'from';
        } else {
            calculationDirection = (inputType === 'coin') ? 'from' : 'to';
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

                // Hiển thị thông tin phí/ngưỡng (chỉ khi Mua)
                if (currentMode === 'buy' && inputType === 'coin') {
                    let threshold = data.threshold_info || 0;
                    let feeToShow = data.fee_applied || 0;
                    let currentRate = current_rates[currentCoin] ? current_rates[currentCoin].buy : 0;
                    let baseRateText = `1 ${currentCoin.toUpperCase()} = ${numberFormat(currentRate, 0)} VNĐ`;

                    if (threshold > 0) {
                        if (amountIn > 0 && amountIn < threshold) {
                            $('#rate-display').html(`${baseRateText} <br> <span style="color:#d9534f;">Phí giao dịch: ${numberFormat(feeToShow)} đ</span> <br> <small style="color:#28a745; font-weight:bold;">💡 Mua >= ${numberFormat(threshold)} để Miễn Phí!</small>`);
                        } else if (amountIn >= threshold) {
                            $('#rate-display').html(`${baseRateText} <br> <span style="color:#28a745; font-weight:bold;">🎉 Đã đạt ngưỡng miễn phí giao dịch!</span>`);
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
                isCalculating = false;
            }
        });
    }

    // --- 3. CÁC HÀM HỖ TRỢ GIAO DIỆN ---
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
        $(`#buy-sell-tabs a[href="#${currentMode}-tab"]`).parent().addClass('active');

        $('#coin-balance').text('Số dư: 0.00 ' + currentCoin.toUpperCase());
        $('#input-coin').val('0.00');
        $('#input-vnd').val('0.00');
        updatePrices();
    }

    function updateRateDisplay(rates) {
        let rate = 0;
        let coinName = currentCoin.toUpperCase();

        if (rates[currentCoin]) {
            rate = (currentMode === 'buy') ? rates[currentCoin].buy : rates[currentCoin].sell;
        }
        $('#rate-display').text(`Với giá: 1 ${coinName} = ${numberFormat(rate, 0)} VNĐ`);
    }

    function updateBalanceDisplay() {
        if (!window.siteLiquidity) return;
        let coinBal = 0;

        // Map coin name với key trong config liquidity
        if (currentCoin === 'bustabit' || currentCoin === 'btc') coinBal = window.siteLiquidity.btc;
        else if (currentCoin === 'ether' || currentCoin === 'eth') coinBal = window.siteLiquidity.eth;
        else if (window.siteLiquidity[currentCoin]) coinBal = window.siteLiquidity[currentCoin];

        $('#input-coin').closest('.swap-field').find('.balance-info').text(`Số dư hệ thống: ${numberFormat(coinBal, 2)} ${currentCoin.toUpperCase()}`);
    }

    function validateLiquidity() {
        if (currentMode !== 'buy' || !window.siteLiquidity) {
            $('#btn-submit-swap').prop('disabled', false).text('Tiếp tục');
            $('#input-coin').css('border-color', '#ccc');
            $('#liquidity-warning').remove();
            return true;
        }

        let amountCoin = parseFloat($('#input-coin').val().replace(/,/g, '')) || 0;
        let limit = 1000000;

        if (currentCoin === 'bustabit' || currentCoin === 'btc') limit = window.siteLiquidity.btc;
        else if (currentCoin === 'ether' || currentCoin === 'eth') limit = window.siteLiquidity.eth;
        else if (window.siteLiquidity[currentCoin]) limit = window.siteLiquidity[currentCoin];

        if (amountCoin > limit) {
            $('#btn-submit-swap').prop('disabled', true).text('Vượt quá số dư hệ thống');
            $('#input-coin').css('border-color', 'red');
            if ($('#liquidity-warning').length === 0) {
                $('#input-coin').parent().after(`<div id="liquidity-warning" style="color:red; font-size:12px; margin-top:5px;">Hệ thống chỉ còn ${numberFormat(limit, 2)} ${currentCoin.toUpperCase()}</div>`);
            } else {
                $('#liquidity-warning').text(`Hệ thống chỉ còn ${numberFormat(limit, 2)} ${currentCoin.toUpperCase()}`);
            }
            return false;
        } else {
            $('#btn-submit-swap').prop('disabled', false).text('Tiếp tục');
            $('#input-coin').css('border-color', '#ccc');
            $('#liquidity-warning').remove();
            return true;
        }
    }

    function validateInput(input) {
        let value = input.value.replace(/[^0-9.]/g, '');
        if ((value.match(/\./g) || []).length > 1) value = value.replace(/\.+$/, "");
        if (value !== input.value) input.value = value;
    }

    function loadSiteConfig() {
        $.ajax({
            url: API_URL + "/api/site-config",
            type: 'GET',
            success: function (res) {
                if (res.success) {
                    if (res.fee_table) $('#fee-table-body').html(res.fee_table);
                    window.siteLiquidity = res.liquidity;
                    updateBalanceDisplay();
                }
            }
        });
    }

    function loadPublicHistory() {
        $.ajax({
            url: API_URL + "/api/public-transactions",
            type: 'GET',
            success: function (response) {
                const historyTableBody = $('#history-table-body');
                if (response.success && response.transactions.length > 0) {
                    historyTableBody.empty();
                    response.transactions.forEach(tx => {
                        const typeHtml = (tx.mode === 'Mua' || tx.mode === 'buy')
                            ? `<span class="tx-buy"><i class="fa fa-arrow-down"></i> Mua</span>`
                            : `<span class="tx-sell"><i class="fa fa-arrow-up"></i> Bán</span>`;

                        const row = `<tr>
                            <td>${typeHtml}</td>
                            <td style="font-weight:600; color:#333;">${escapeHTML(tx.coin)}</td>
                            <td class="text-right" style="font-family:monospace; font-size:13px;">${numberFormat(tx.amount_coin, 2)}</td>
                            <td class="text-right text-muted" style="font-size:12px;">${escapeHTML(tx.created_at)}</td>
                        </tr>`;
                        historyTableBody.append(row);
                    });
                } else {
                    historyTableBody.html('<tr><td colspan="4" class="text-center" style="padding:20px;">Chưa có giao dịch nào.</td></tr>');
                }
            }
        });
    }

    // --- 4. SỰ KIỆN (EVENTS) ---
    $('#input-coin, #input-vnd').on('input', function () { validateInput(this); });
    $('#input-coin, #input-vnd').on('paste', function (e) {
        let pastedData = e.originalEvent.clipboardData.getData('text');
        if (!/^[0-9.]+$/.test(pastedData)) { e.preventDefault(); alert("Vui lòng chỉ dán số!"); }
    });

    $('#input-coin').on('keyup', function () { calculateSwap('coin', parseFloat($(this).val().replace(/,/g, '')) || 0); });
    $('#input-vnd').on('keyup', function () { calculateSwap('vnd', parseFloat($(this).val().replace(/,/g, '')) || 0); });

    $('#buy-sell-tabs a').on('click', function (e) {
        e.preventDefault();
        let newMode = $(this).attr('href') === '#buy-tab' ? 'buy' : 'sell';
        if (newMode !== currentMode) {
            currentMode = newMode;
            updateFormUI();
        }
    });

    $('#coin-list a').on('click', function (e) {
        e.preventDefault();
        let coinText = $(this).text();
        let coinIcon = $(this).data('icon');
        currentCoin = $(this).data('coin');

        $('#coin-text').text(coinText);
        $('#coin-icon').attr('src', coinIcon);
        $('#coin-balance').text('Số dư: 0 ' + currentCoin.toUpperCase());

        updatePrices();
        calculateSwap('vnd', parseFloat($('#input-vnd').val().replace(/,/g, '')) || 0);
        updateBalanceDisplay();
    });

    $('#btn-submit-swap').on('click', function () {
        if (!localStorage.getItem('buser_user')) {
            window.location.href = "login.html";
            return;
        }
        let amountCoin = parseFloat($('#input-coin').val().replace(/,/g, '')) || 0;
        let amountVND = parseFloat($('#input-vnd').val().replace(/,/g, '')) || 0;

        if (amountCoin === 0 || amountVND === 0) {
            alert("Vui lòng nhập số lượng hợp lệ.");
            return;
        }

        let amount_from = (currentMode === 'buy') ? amountVND : amountCoin;
        let amount_to = (currentMode === 'buy') ? amountCoin : amountVND;

        var draftOrder = { mode: currentMode, coin: currentCoin, amount_from: amount_from, amount_to: amount_to };
        localStorage.setItem('draft_order', JSON.stringify(draftOrder));

        window.location.href = (currentMode === 'buy') ? "checkout_select_wallet.html" : "checkout_select_bank.html";
    });

    // --- 5. KHỞI CHẠY ---
    loadSiteConfig();
    updatePrices();
    setInterval(updatePrices, 15000); // Tự động cập nhật giá mỗi 15s
    updateFormUI();
    loadPublicHistory();
});