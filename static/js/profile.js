$(document).ready(function () {

    // --- 1. LOGIC TRANG HỒ SƠ (profile.html) ---
    // Chỉ chạy khi đang ở trang profile (có form đổi pass)
    if ($('#change-pass-form').length > 0) {

        // Load thông tin user từ localStorage
        const userDataString = localStorage.getItem('buser_user');
        if (userDataString) {
            const user = JSON.parse(userDataString);
            $('#profile-email').val(user.email);
        } else {
            window.location.href = "login.html";
        }

        // Xử lý Tabs (Lazy Load - Chỉ tải khi bấm vào tab)
        let historyLoaded = false;
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
                walletsLoaded = true;
            }
        });

        let banksLoaded = false;
        $('a[data-toggle="tab"][href="#banks"]').on('shown.bs.tab', function (e) {
            if (!banksLoaded) {
                loadBanksList();
                banksLoaded = true;
            }
        });
    }

    // --- 2. CÁC HÀM TẢI DỮ LIỆU ---

    // Tải lịch sử cá nhân
    let myHistoryPage = 1;
    let myHistoryTotal = 1;

    function loadPersonalHistory(page = 1) {
        if (!localStorage.getItem('buser_user')) return;

        $('#personal-history-body').html('<tr><td colspan="7" class="text-center"><i class="fa fa-spinner fa-spin"></i> Đang tải...</td></tr>');

        $.ajax({
            url: API_URL + "/api/user/my-transactions",
            type: 'GET',
            data: { page: page },
            success: function (response) {
                const historyBody = $('#personal-history-body');
                historyBody.empty();

                if (response.success && response.transactions.length > 0) {
                    if (response.pagination) {
                        myHistoryPage = response.pagination.current_page;
                        myHistoryTotal = response.pagination.total_pages;
                        $('#his-page').text(myHistoryPage);

                        $('#btn-his-prev').prop('disabled', myHistoryPage <= 1);
                        $('#btn-his-next').prop('disabled', myHistoryPage >= myHistoryTotal);
                    }

                    response.transactions.forEach(tx => {
                        const amountCoin = numberFormat(tx.amount_coin, 8);
                        const amountVND = numberFormat(tx.amount_vnd, 0);
                        let statusClass = 'label-success';
                        if (tx.status_vi.includes('Đang chờ')) statusClass = 'label-warning';
                        else if (tx.status_vi.includes('Đã hủy')) statusClass = 'label-danger';

                        let linkUrl = "";
                        if (tx.status_vi.includes("Đã hoàn thành") || tx.status_vi.includes("Đã hủy")) {
                            linkUrl = `/transaction/${tx.id}`;
                        } else {
                            let pageName = tx.mode.toLowerCase().includes('mua') ? 'checkout_payment_buy.html' : 'checkout_payment_sell.html';
                            linkUrl = `${pageName}?id=${tx.id}`;
                        }

                        const idLink = `<a href="${linkUrl}" style="font-weight:bold; text-decoration:underline;">${escapeHTML(tx.id)}</a>`;
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
                    historyBody.html('<tr><td colspan="7" class="text-center">Chưa có giao dịch nào.</td></tr>');
                }
            },
            error: function () {
                $('#personal-history-body').html('<tr><td colspan="7" class="text-center">Lỗi tải dữ liệu.</td></tr>');
            }
        });
    }

    // Sự kiện phân trang lịch sử
    $(document).on('click', '#btn-his-prev', function () {
        if (myHistoryPage > 1) loadPersonalHistory(myHistoryPage - 1);
    });
    $(document).on('click', '#btn-his-next', function () {
        if (myHistoryPage < myHistoryTotal) loadPersonalHistory(myHistoryPage + 1);
    });

    // Tải danh sách Ví
    function loadWalletsList() {
        if (!localStorage.getItem('buser_user')) return;

        const tableBody = $('#wallets-table-body');
        const coins = ['bustabit', 'usdt', 'usdc', 'ether', 'bnb', 'sol', 'itlg', 'itl'];

        let requests = coins.map(coin => {
            return $.ajax({ url: `${API_URL}/api/user/wallets?coin_type=${coin}`, type: 'GET' });
        });

        tableBody.html('<tr><td colspan="4" class="text-center"><i class="fa fa-spinner fa-spin"></i> Đang tải dữ liệu...</td></tr>');

        $.when.apply($, requests).done(function () {
            tableBody.empty();
            let allWallets = [];

            if (coins.length === 1) {
                if (arguments[0].wallets) allWallets = allWallets.concat(arguments[0].wallets);
            } else {
                for (let i = 0; i < arguments.length; i++) {
                    let res = arguments[i][0];
                    if (res && res.wallets) allWallets = allWallets.concat(res.wallets);
                }
            }

            if (allWallets.length === 0) {
                tableBody.html('<tr><td colspan="4" class="text-center">Bạn chưa lưu ví nào.</td></tr>');
                return;
            }

            allWallets.forEach(wallet => {
                let type = escapeHTML(wallet.coin_type.toUpperCase());
                let mainInfoLabel = "Địa chỉ";
                let mainInfoValue = escapeHTML(wallet.address);
                let details = "";

                if (wallet.coin_type === 'ether') {
                    mainInfoLabel = "Ethos ID";
                    details = `<b>Tên:</b> ${escapeHTML(wallet.name)}<br><b>SĐT:</b> ${escapeHTML(wallet.phone)}`;
                } else if (wallet.coin_type === 'bustabit') {
                    let tagShow = (wallet.tag && wallet.tag !== 'null') ? wallet.tag : 'N/A';
                    details = `<b>Tag:</b> ${escapeHTML(tagShow)}<br><b>Tên:</b> ${escapeHTML(wallet.name)}<br><b>SĐT:</b> ${escapeHTML(wallet.phone)}`;
                } else {
                    details = `<b>Tên:</b> ${escapeHTML(wallet.name)}<br><b>SĐT:</b> ${escapeHTML(wallet.phone)}`;
                }

                const row = `
                <tr id="wallet-row-${escapeHTML(wallet.id)}">
                    <td><span class="label label-primary">${type}</span></td>
                    <td><small class="text-muted">${mainInfoLabel}:</small><br><strong>${mainInfoValue}</strong></td>
                    <td><small>${details}</small></td>
                    <td><button class="btn btn-xs btn-danger btn-delete-wallet" data-id="${escapeHTML(wallet.id)}"><i class="fa fa-trash"></i> Xóa</button></td>
                </tr>`;
                tableBody.append(row);
            });
        }).fail(function () {
            tableBody.html('<tr><td colspan="4" class="text-center text-danger">Lỗi khi tải dữ liệu ví.</td></tr>');
        });
    }

    // Tải danh sách Ngân hàng
    function loadBanksList() {
        if (!localStorage.getItem('buser_user')) return;
        const tableBody = $('#banks-table-body');

        $.ajax({
            url: `${API_URL}/api/user/banks`,
            type: 'GET',
            success: function (response) {
                tableBody.empty();
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

    // --- 3. CÁC FORM CẬP NHẬT TÀI KHOẢN ---

    $('#change-pass-form').on('submit', function (e) {
        e.preventDefault();
        let newPass = $(this).find('input[name="new_password"]').val();
        let confirmPass = $(this).find('input[name="confirm_password"]').val();
        if (newPass !== confirmPass) { alert("Lỗi: Mật khẩu mới không khớp!"); return; }

        var data = {
            old_password: $(this).find('input[name="old_password"]').val(),
            new_password: newPass
        };
        $.ajax({
            url: API_URL + "/api/change-password",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function (response) { alert(response.message); $('#change-pass-form')[0].reset(); },
            error: function (xhr) { alert("Lỗi: " + xhr.responseJSON.message); }
        });
    });

    $('#change-email-form').on('submit', function (e) {
        e.preventDefault();
        var data = { new_email: $(this).find('input[name="new_email"]').val() };
        $.ajax({
            url: API_URL + "/api/change-email",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function (response) {
                alert(response.message);
                const userDataString = localStorage.getItem('buser_user');
                if (userDataString) {
                    let user = JSON.parse(userDataString);
                    user.email = data.new_email;
                    localStorage.setItem('buser_user', JSON.stringify(user));
                }
            },
            error: function (xhr) { alert("Lỗi: " + xhr.responseJSON.message); }
        });
    });

    // Xóa Ví & Bank
    $(document).on('click', '.btn-delete-wallet', function () {
        const walletId = $(this).data('id');
        if (!confirm('Bạn có chắc chắn muốn xóa ví này không?')) return;
        $.ajax({
            url: `${API_URL}/api/user/delete-wallet`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ wallet_id: walletId }),
            success: function (response) { alert(response.message); $(`#wallet-row-${walletId}`).fadeOut(500, function () { $(this).remove(); }); },
            error: function (xhr) { alert('Lỗi: ' + xhr.responseJSON.message); }
        });
    });

    $(document).on('click', '.btn-delete-bank', function () {
        const bankId = $(this).data('id');
        if (!confirm('Bạn có chắc chắn muốn xóa ngân hàng này không?')) return;
        $.ajax({
            url: `${API_URL}/api/user/delete-bank`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ bank_id: bankId }),
            success: function (response) { alert(response.message); $(`#bank-row-${bankId}`).fadeOut(500, function () { $(this).remove(); }); },
            error: function (xhr) { alert('Lỗi: ' + xhr.responseJSON.message); }
        });
    });

    // --- 4. TRANG THÊM VÍ (add-wallet.html) ---
    if ($('#add-wallet-form').length > 0) {
        function toggleWalletFields() {
            const type = $('#coin-type-select').val();
            $('#field-address-group').show();
            $('#field-tag-group').hide();
            $('#field-personal-group').show();

            if (type === 'bustabit') {
                $('#field-tag-group').show();
                $('#label-tag').text('Destination Tag:');
            } else if (type === 'ether') {
                $('#field-address-group').hide();
                $('#field-tag-group').show();
                $('#label-tag').text('Ethos ID (Destination Tag):');
            } else if (type === 'itlg' || type === 'itl') {
                $('label[for="input-address"]').text("Địa chỉ Ví / ID Tài khoản:");
                $('#field-tag-group').hide();
            }
            if (type === 'bustabit' || type === 'bnb' || type === 'sol') {
                $('#field-tag-group').show();
                $('#label-tag').text(type === 'bustabit' ? 'Destination Tag:' : 'Memo (Nếu có):');
            }
        }
        toggleWalletFields();
        $('#coin-type-select').on('change', toggleWalletFields);

        $('#add-wallet-form').on('submit', function (e) {
            e.preventDefault();
            var coinType = $(this).find('select[name="coin_type"]').val();
            var inputAddress = $(this).find('input[name="address"]').val();
            var inputTag = $(this).find('input[name="tag"]').val();
            var inputName = $(this).find('input[name="name"]').val();
            var inputPhone = $(this).find('input[name="phone"]').val();

            if (coinType === 'ether') {
                if (!inputTag) { alert("Vui lòng nhập Ethos ID (Tag)!"); return; }
                inputAddress = inputTag;
            } else if (coinType !== 'ether' && !inputAddress) {
                alert("Vui lòng nhập địa chỉ ví!"); return;
            }

            if (!inputName || !inputPhone) { alert("Vui lòng nhập đầy đủ Họ tên và Số điện thoại!"); return; }

            var data = { coin_type: coinType, address: inputAddress, tag: inputTag, name: inputName, phone: inputPhone };
            $.ajax({
                url: API_URL + "/api/user/add-wallet",
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(data),
                success: function (response) {
                    alert(response.message);
                    if (document.referrer && document.referrer.includes('profile.html')) window.location.href = "profile.html#wallets";
                    else window.location.href = "checkout_select_wallet.html";
                },
                error: function (xhr) { alert("Lỗi: " + (xhr.responseJSON ? xhr.responseJSON.message : "Lỗi không xác định")); }
            });
        });
    }

    // --- 5. TRANG THÊM BANK (add-bank.html) ---
    if ($('#add-bank-form').length > 0) {
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
                    if (document.referrer && document.referrer.includes('profile.html')) window.location.href = "profile.html#banks";
                    else window.location.href = "checkout_select_bank.html";
                },
                error: function (xhr) { alert("Lỗi: " + xhr.responseJSON.message); }
            });
        });
    }
});