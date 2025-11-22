// --- Hàm định dạng số ---
function numberFormat(number = '0', decimalPlaces = 0) {
    let val = parseFloat(number);
    if (isNaN(val)) return "0";

    // 1. Lấy số thập phân cố định
    let fixed = val.toFixed(decimalPlaces);

    // 2. Tách phần nguyên và phần thập phân
    let parts = fixed.split('.');
    let integerPart = parts[0];
    let decimalPart = parts.length > 1 ? parts[1] : '';

    // 3. Thêm dấu phẩy vào phần nguyên
    integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');

    // 4. Xử lý phần thập phân: Xóa số 0 thừa ở cuối
    if (decimalPlaces > 0) {
        decimalPart = decimalPart.replace(/0+$/, ''); // Xóa 0 cuối
        if (decimalPart.length > 0) {
            return integerPart + '.' + decimalPart; // Nếu còn số thì ghép vào
        }
    }

    return integerPart; // Nếu không còn số thập phân
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

$(document).ready(function () {

    // --- Biến toàn cục ---
    let currentMode = 'buy';
    let currentCoin = 'bustabit';
    let isCalculating = false;

    // --- Hàm gọi API lấy giá (Cập nhật Bảng giá) ---
    function updatePrices() {
        $.get(API_URL + "/api/prices", function (data) {
            if (data.ether) {
                $('#ether-buy').text(numberFormat(data.ether.buy, 0) + ' ₫');
                $('#ether-sell').text(numberFormat(data.ether.sell, 0) + ' ₫');
            }
            if (data.bustabit) {
                $('#bustabit-buy').text(numberFormat(data.bustabit.buy, 0) + ' ₫');
                $('#bustabit-sell').text(numberFormat(data.bustabit.sell, 0) + ' ₫');
            }
            if (data.btc) {
                $('#btc-buy').text(numberFormat(data.btc.buy, 0) + ' ₫');
                $('#btc-sell').text(numberFormat(data.btc.sell, 0) + ' ₫');
            }
            if (data.usdt) {
                $('#usdt-buy').text(numberFormat(data.usdt.buy, 0) + ' ₫');
                $('#usdt-sell').text(numberFormat(data.usdt.sell, 0) + ' ₫');
            }
            if (data.eth) {
                $('#eth-buy').text(numberFormat(data.eth.buy, 0) + ' ₫');
                $('#eth-sell').text(numberFormat(data.eth.sell, 0) + ' ₫');
            }
            if (data.bnb) {
                $('#bnb-buy').text(numberFormat(data.bnb.buy, 0) + ' ₫');
                $('#bnb-sell').text(numberFormat(data.bnb.sell, 0) + ' ₫');
            }
            if (data.doge) {
                $('#doge-buy').text(numberFormat(data.doge.buy, 0) + ' ₫');
                $('#doge-sell').text(numberFormat(data.doge.sell, 0) + ' ₫');
            }
            if (data.sol) {
                $('#sol-buy').text(numberFormat(data.sol.buy, 0) + ' ₫');
                $('#sol-sell').text(numberFormat(data.sol.sell, 0) + ' ₫');
            }
            if (data.ada) {
                $('#ada-buy').text(numberFormat(data.ada.buy, 0) + ' ₫');
                $('#ada-sell').text(numberFormat(data.ada.sell, 0) + ' ₫');
            }
            if (data.xrp) {
                $('#xrp-buy').text(numberFormat(data.xrp.buy, 0) + ' ₫');
                $('#xrp-sell').text(numberFormat(data.xrp.sell, 0) + ' ₫');
            }
            if (data.xlm) {
                $('#xlm-buy').text(numberFormat(data.xlm.buy, 0) + ' ₫');
                $('#xlm-sell').text(numberFormat(data.xlm.sell, 0) + ' ₫');
            }
            if (data.ltc) {
                $('#ltc-buy').text(numberFormat(data.ltc.buy, 0) + ' ₫');
                $('#ltc-sell').text(numberFormat(data.ltc.sell, 0) + ' ₫');
            }
            if (data.cake) {
                $('#cake-buy').text(numberFormat(data.cake.buy, 0) + ' ₫');
                $('#cake-sell').text(numberFormat(data.cake.sell, 0) + ' ₫');
            }
            if (data.near) {
                $('#cake-buy').text(numberFormat(data.cake.buy, 0) + ' ₫');
                $('#cake-sell').text(numberFormat(data.cake.sell, 0) + ' ₫');
            }
            updateRateDisplay(data);
        }).fail(function () {
            console.error("Không thể kết nối đến API backend " + API_URL);
            $('.rate_buy, .rate_sell').text("Lỗi API").css('color', 'red');
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

        // Logic mới: direction 'from'/'to' giờ phụ thuộc vào inputType và currentMode
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
            contentType: 'application/json',
            data: JSON.stringify({
                amount: amountIn,
                direction: calculationDirection,
                mode: currentMode,
                coin: currentCoin
            }),
            success: function (data) {
                if (inputType === 'coin') {
                    // Gõ vào ô Coin, cập nhật ô VNĐ
                    $('#input-vnd').val(numberFormat(data.amount_out, 0));
                } else { // inputType === 'vnd'
                    // Gõ vào ô VNĐ, cập nhật ô Coin
                    $('#input-coin').val(numberFormat(data.amount_out, 8));
                }
                isCalculating = false;
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

        $('#coin-balance').text('Số dư: --- ' + currentCoin.toUpperCase());
        $('#input-coin').val('---');
        $('#input-vnd').val('---');
        updatePrices();
    }

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

    function updateBalanceDisplay() {
        if (!window.siteLiquidity) return;

        // Cập nhật số dư VNĐ
        $('#input-vnd').closest('.swap-field').find('.balance-info').text(`Số dư hệ thống: ${numberFormat(window.siteLiquidity.vnd, 0)} VNĐ`);

        // Cập nhật số dư Coin (Tùy coin đang chọn)
        let coinBal = 0;
        let unit = currentCoin.toUpperCase();

        if (currentCoin === 'bustabit' || currentCoin === 'btc') {
            coinBal = window.siteLiquidity.btc; // Bits/BTC
            unit = 'Bits';
        } else if (currentCoin === 'usdt') {
            coinBal = window.siteLiquidity.usdt;
        } else {
            coinBal = 0; // Mặc định cho coin mới nếu chưa set
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

    // --- HÀM HỖ TRỢ XÁC THỰC ---
    function getAuthToken() {
        const loginDataString = localStorage.getItem('buser_login_data');
        if (!loginDataString) return null;
        try {
            const loginData = JSON.parse(loginDataString);
            return loginData.token; // Lấy token (là username)
        } catch (e) {
            return null;
        }
    }

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
        } else {
            $('#menu-register').show();
            $('#menu-login').show();
            $('#menu-profile').hide();
            $('#menu-admin').hide();
            $('#menu-logout').hide();
            $('#btn-submit-swap').text('Đăng Nhập / Đăng Ký').removeClass('btn-success').addClass('btn-primary');
        }
    }

    // --- [MỚI] Hàm tải Lịch sử Giao dịch Công khai ---
    function loadPublicHistory() {
        $.ajax({
            url: API_URL + "/api/public-transactions",
            type: 'GET',
            success: function (response) {
                const historyTableBody = $('#history-table-body');
                if (response.success && response.transactions.length > 0) {
                    historyTableBody.empty();
                    response.transactions.forEach(tx => {
                        const amountFormatted = numberFormat(tx.amount_coin, 2);
                        const row = `
                     <tr>
                     <td class="left">${escapeHTML(tx.mode)}</td>
                     <td>${escapeHTML(tx.coin)}</td>
                     <td class="center">${amountFormatted}</td>
                     <td class="center">${escapeHTML(tx.created_at)}</td>
                     </tr>`;
                        historyTableBody.append(row);
                    });
                } else {
                    historyTableBody.html('<tr><td colspan="4" class="text-center">Chưa có lịch sử giao dịch.</td></tr>');
                }
            },
            error: function () {
                $('#history-table-body').html('<tr><td colspan="4" class="text-center">Lỗi khi tải lịch sử.</td></tr>');
            }
        });
    }

    // --- [MỚI] Hàm tải Lịch sử Giao dịch CÁ NHÂN ---
    function loadPersonalHistory() {
        const token = getAuthToken();
        if (!token) {
            $('#personal-history-body').html('<tr><td colspan="6" class="text-center">Lỗi: Bạn chưa đăng nhập.</td></tr>');
            return;
        }

        $.ajax({
            url: API_URL + "/api/user/my-transactions",
            type: 'GET',
            beforeSend: function (xhr) {
                xhr.setRequestHeader('Authorization', 'Bearer ' + token);
            },
            success: function (response) {
                const historyBody = $('#personal-history-body');
                if (response.success && response.transactions.length > 0) {
                    historyBody.empty(); // Xóa "Đang tải..."
                    response.transactions.forEach(tx => {
                        // Định dạng số
                        const amountCoin = numberFormat(tx.amount_coin, 8);
                        const amountVND = numberFormat(tx.amount_vnd, 0);
                        // Tô màu trạng thái
                        let statusClass = 'label-success'; // Hoàn thành
                        if (tx.status_vi.includes('Đang chờ')) {
                            statusClass = 'label-warning'; // Đang chờ
                        } else if (tx.status_vi.includes('Đã hủy')) {
                            statusClass = 'label-danger'; // Hủy
                        }

                        let linkPage = tx.mode === 'Mua' ? 'checkout_payment_buy.html' : 'checkout_payment_sell.html';
                        // Lưu ý: API trả về tx.mode là tiếng Việt hoặc Anh tùy lúc, kiểm tra kỹ. 
                        // Trong app.py ta để "Mua"/"Bán".
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
                $('#personal-history-body').html('<tr><td colspan="6" class="text-center">Lỗi khi tải lịch sử: ${xhr.responseJSON.message}</td></tr>');
            }
        });
    }

    // --- [MỚI] Hàm tải danh sách VÍ (Wallet) đã lưu ---
    function loadWalletsList() {
        const token = getAuthToken();
        const tableBody = $('#wallets-table-body');

        // Gọi API cho cả 2 loại coin
        const req1 = $.ajax({
            url: `${API_URL}/api/user/wallets?coin_type=bustabit`,
            type: 'GET',
            beforeSend: function (xhr) { xhr.setRequestHeader('Authorization', 'Bearer ' + token); }
        });
        const req2 = $.ajax({
            url: `${API_URL}/api/user/wallets?coin_type=usdt`,
            type: 'GET',
            beforeSend: function (xhr) { xhr.setRequestHeader('Authorization', 'Bearer ' + token); }
        });

        // Dùng $.when để đợi cả 2 API cùng chạy xong
        $.when(req1, req2).done(function (res1, res2) {
            tableBody.empty(); // Xóa "Đang tải..."
            const wallets = res1[0].wallets.concat(res2[0].wallets); // Gộp 2 mảng kết quả

            if (wallets.length === 0) {
                tableBody.html('<tr><td colspan="4" class="text-center">Bạn chưa lưu ví nào.</td></tr>');
                return;
            }

            wallets.forEach(wallet => {
                let type = escapeHTML(wallet.coin_type.toUpperCase());
                let address = escapeHTML(wallet.address);
                let name = escapeHTML(wallet.name);
                let details = `Tag: ${escapeHTML(wallet.tag) || 'N/A'}<br>Phone: ${escapeHTML(wallet.phone) || 'N/A'}`;
                if (wallet.coin_type === 'usdt') {
                    details = "(Không yêu cầu chi tiết)";
                }

                const row = `
                <tr id="wallet-row-${escapeHTML(wallet.id)}">
                <td>${type}</td>
                <td><b>${name || 'Chưa đặt tên'}</b><br><small>${address}</small></td>
                <td><small>${details}</small></td>
                <td><button class="btn btn-xs btn-danger btn-delete-wallet" data-id="${escapeHTML(wallet.id)}"><i class="fa fa-trash"></i> Xóa</button></td>
                </tr>`;
                tableBody.append(row);
            });
        }).fail(function () {
            tableBody.html('<tr><td colspan="4" class="text-center">Lỗi khi tải danh sách ví.</td></tr>');
        });
    }

    // --- [MỚI] Hàm tải danh sách NGÂN HÀNG (Bank) đã lưu ---
    function loadBanksList() {
        const token = getAuthToken();
        const tableBody = $('#banks-table-body');

        $.ajax({
            url: `${API_URL}/api/user/banks`,
            type: 'GET',
            beforeSend: function (xhr) { xhr.setRequestHeader('Authorization', 'Bearer ' + token); },
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
            beforeSend: function (xhr) {
                xhr.setRequestHeader('Authorization', 'Bearer ' + getAuthToken());
            },
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
            beforeSend: function (xhr) {
                xhr.setRequestHeader('Authorization', 'Bearer ' + getAuthToken());
            },
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
        localStorage.removeItem('buser_user');
        localStorage.removeItem('buser_login_data'); // Xóa cả token
        alert("Đăng xuất thành công!");
        window.location.href = "index.html";
    });

    // --- XỬ LÝ FORM ĐĂNG KÝ ---
    $("#register-form").on('submit', function (e) {
        e.preventDefault();
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
                localStorage.setItem('buser_login_data', JSON.stringify(response));
                window.location.href = "index.html";
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
            }
        });
    });

    // --- XỬ LÝ NÚT "TIẾP TỤC" (LƯU LỰA CHỌN) ---
    $('#btn-submit-swap').on('click', function () {
        const token = getAuthToken();
        if (!token) {
            window.location.href = "login.html";
            return;
        }

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
            beforeSend: function (xhr) {
                // [ĐÃ SỬA LỖI] 'Bearer ' +
                xhr.setRequestHeader('Authorization', 'Bearer ' + getAuthToken());
            },
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
            beforeSend: function (xhr) {
                // [ĐÃ SỬA LỖI] 'Bearer ' +
                xhr.setRequestHeader('Authorization', 'Bearer ' + getAuthToken());
            },
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
    if ($('#settings-form').length > 0) {
        $.ajax({
            url: API_URL + "/api/admin/settings",
            type: 'GET',
            beforeSend: function (xhr) {
                // [ĐÃ SỬA LỖI] 'Bearer ' +
                xhr.setRequestHeader('Authorization', 'Bearer ' + getAuthToken());
            },
            success: function (response) {
                if (response.success) {
                    $('input[name="admin_bank_bin"]').val(response.settings.admin_bank_bin);
                    $('input[name="admin_account_number"]').val(response.settings.admin_account_number);
                    $('input[name="admin_account_name"]').val(response.settings.admin_account_name);
                    $('input[name="admin_bustabit_id"]').val(response.settings.admin_bustabit_id);
                    $('input[name="admin_usdt_wallet"]').val(response.settings.admin_usdt_wallet);
                    $('input[name="telegram_bot_token"]').val(response.settings.TELEGRAM_BOT_TOKEN || '');
                    $('input[name="telegram_chat_id"]').val(response.settings.TELEGRAM_CHAT_ID || '');
                    $('input[name="liquidity_vnd"]').val(response.settings.liquidity_vnd);
                    $('input[name="liquidity_usdt"]').val(response.settings.liquidity_usdt);
                    $('input[name="liquidity_btc"]').val(response.settings.liquidity_btc);
                    $('input[name="liquidity_eth"]').val(response.settings.liquidity_eth);
                    $('input[name="liquidity_bnb"]').val(response.settings.liquidity_bnb);
                    $('input[name="liquidity_sol"]').val(response.settings.liquidity_sol);
                    $('textarea[name="fee_html_content"]').val(response.settings.fee_html_content);
                }
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
                window.location.href = "index.html";
            }
        });
    }

    $('#settings-form').on('submit', function (e) {
        e.preventDefault();
        var settingsData = {
            admin_bank_bin: $('input[name="admin_bank_bin"]').val(),
            admin_account_number: $('input[name="admin_account_number"]').val(),
            admin_account_name: $('input[name="admin_account_name"]').val(),
            admin_bustabit_id: $('input[name="admin_bustabit_id"]').val(),
            admin_usdt_wallet: $('input[name="admin_usdt_wallet"]').val(),
            TELEGRAM_BOT_TOKEN: $('input[name="telegram_bot_token"]').val(),
            TELEGRAM_CHAT_ID: $('input[name="telegram_chat_id"]').val(),
            liquidity_vnd: $('input[name="liquidity_vnd"]').val(),
            liquidity_usdt: $('input[name="liquidity_usdt"]').val(),
            liquidity_btc: $('input[name="liquidity_btc"]').val(),
            liquidity_eth: $('input[name="liquidity_eth"]').val(),
            liquidity_bnb: $('input[name="liquidity_bnb"]').val(),
            liquidity_sol: $('input[name="liquidity_sol"]').val(),
            fee_html_content: $('textarea[name="fee_html_content"]').val(),
        };
        $.ajax({
            url: API_URL + "/api/admin/settings",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(settingsData),
            beforeSend: function (xhr) {
                // [ĐÃ SỬA LỖI] 'Bearer ' +
                xhr.setRequestHeader('Authorization', 'Bearer ' + getAuthToken());
            },
            success: function (response) { alert(response.message); },
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


    // --- XỬ LÝ FORM THÊM VÍ (add-wallet.html) ---
    $('#add-wallet-form').on('submit', function (e) {
        e.preventDefault();

        var data = {
            coin_type: $(this).find('select[name="coin_type"]').val(),
            address: $(this).find('input[name="address"]').val(),
            tag: $(this).find('input[name="tag"]').val(),
            name: $(this).find('input[name="name"]').val(),
            phone: $(this).find('input[name="phone"]').val()
        };

        // Ẩn/hiện trường theo logic
        if (data.coin_type === 'usdt') {
            data.tag = "";
            data.name = "";
            data.phone = "";
        }

        $.ajax({
            url: API_URL + "/api/user/add-wallet",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            beforeSend: function (xhr) {
                xhr.setRequestHeader('Authorization', 'Bearer ' + getAuthToken());
            },
            success: function (response) {
                alert(response.message); // "Đã thêm ví thành công!"
                if (document.referrer && document.referrer.includes('profile.html')) {
                    window.location.href = "profile.html#wallets";
                } else {
                    window.location.href = "checkout_select_wallet.html";
                }
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
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
            beforeSend: function (xhr) {
                xhr.setRequestHeader('Authorization', 'Bearer ' + getAuthToken());
            },
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
});