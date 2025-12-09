$(document).ready(function () {

    const socket = io();

    socket.on('admin_new_order', function (data) {
        new Audio('/static/sound/ding.mp3').play();
        console.log("Có đơn mới:", data.order_id);
        loadTransactions();
        alert("🔔 Có đơn hàng mới: " + data.order_id);
    });

    // --- Xử lý nút "Hủy Đơn" (Admin) ---
    $(document).on('click', '.btn-cancel-admin', function () {
        const btn = $(this);
        const orderId = btn.data('id');

        if (!confirm(`ADMIN: Bạn có chắc chắn muốn HỦY đơn hàng ${orderId} không?`)) {
            return;
        }
        setLoading(btn, true, 'Đang gửi...');
        $.ajax({
            url: `${API_URL}/api/admin/cancel-order`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ order_id: orderId }),
            success: function (response) {
                alert(response.message);
                btn.closest('tr').fadeOut(500, function () {
                    $(this).remove();
                    loadTransactions();
                });
            },
            error: function (xhr) {
                setLoading(btn, false);
                alert("Lỗi: " + xhr.responseJSON.message);
            }
        });
    });

    // --- Tải dữ liệu giao dịch ---
    function loadTransactions() {
        $.ajax({
            url: `${API_URL}/api/admin/transactions`,
            type: 'GET',
            success: function (response) {
                if (response.success) {
                    renderTables(response.transactions);

                    if (response.stats) {
                        $('#stat-vnd-in').text(numberFormat(response.stats.total_vnd_in_month, 0) + ' ₫');
                        $('#stat-vnd-out').text(numberFormat(response.stats.total_vnd_out_month, 0) + ' ₫');
                        
                        // Các phần hiển thị coin giữ nguyên
                        $('#stat-bustabit').text(numberFormat(response.stats.total_bustabit_volume, 8));
                        $('#stat-ether').text(numberFormat(response.stats.total_ether_volume, 8));
                        $('#stat-usdt').text(numberFormat(response.stats.total_usdt_volume, 2));
                        $('#stat-bnb').text(numberFormat(response.stats.total_bnb_volume, 4));
                        $('#stat-sol').text(numberFormat(response.stats.total_sol_volume, 4));
                    }
                }
            },

            error: function (xhr) {
                alert("Lỗi tải giao dịch: " + xhr.responseJSON.message);
                window.location.href = "index.html"; // Đá về trang chủ nếu không phải Admin
            }
        });
    }

    let dynamicBinMap = {};

    function loadBinMap() {
        $.ajax({
            url: `${API_URL}/api/config/supported-banks`,
            type: 'GET',
            success: function (res) {
                if (res.success && res.banks) {
                    dynamicBinMap = {};
                    res.banks.forEach(b => {
                        // Map cả tên đầy đủ và tên ngắn vào BIN để dễ tìm
                        dynamicBinMap[b.name] = b.bin;
                        dynamicBinMap[b.short_name] = b.bin;
                    });
                    // Sau khi có map thì mới load giao dịch để đảm bảo render đúng QR
                    loadTransactions();
                }
            }
        });
    }

    // --- Hiển thị dữ liệu lên bảng ---
    function renderTables(transactions) {
        const buyTable = $('#buy-orders-table');
        const sellTable = $('#sell-orders-table');
        buyTable.empty();
        sellTable.empty();

        let buyCount = 0;
        let sellCount = 0;

        transactions.forEach(order => {
            let actionBtns = '';
            if (order.mode === 'buy') {
                actionBtns = `<button class="btn btn-sm btn-primary btn-complete" data-id="${order.id}"><i class="fa fa-check"></i> Đã Gửi Coin</button>`;
            } else {
                actionBtns = `<button class="btn btn-sm btn-warning btn-complete" data-id="${order.id}"><i class="fa fa-check"></i> Đã Chuyển Tiền</button>`;
            }
            actionBtns += `<br><button class="btn btn-sm btn-danger btn-cancel-admin" data-id="${order.id}" style="margin-top:5px;"><i class="fa fa-times"></i> Hủy đơn</button>`;

            let billLink = (order.bill_image && order.bill_image !== 'null') ?
                `<br><a href="${API_URL}/api/admin/bill/${order.bill_image}" target="_blank" class="btn btn-xs btn-info" style="margin-top:5px;"><i class="fa fa-picture-o"></i> Xem Bill</a>` :
                `<br><small style="color:#999;">Chưa có bill</small>`;

            if (order.mode === 'buy') {
                // Bảng MUA: 6 cột
                const row = `
                <tr id="order-${order.id}">
                    <td><a href="checkout_payment_buy.html?id=${order.id}" target="_blank"><strong>${order.id}</strong></a></td>
                    <td>${escapeHTML(order.username)}</td>
                    <td>${numberFormat(order.amount_coin, 8)} ${order.coin.toUpperCase()}</td>
                    <td>${order.coin.toUpperCase()}</td>
                    <td>${order.detail_info} ${billLink}</td> 
                    <td>${actionBtns}</td>
                </tr>`;
                buyTable.append(row);
                buyCount++;
            } else {
                // Bảng BÁN: 5 cột + QR Code + Copy Content
                let qrBtn = '';
                const copyBtn = `<button class="btn btn-xs btn-default" onclick="navigator.clipboard.writeText('${order.sell_content}');alert('Đã copy nội dung!')"><i class="fa fa-copy"></i> Copy ND</button>`;

                if (order.user_bank_raw) {
                    // 1. Tìm mã BIN dựa trên tên ngân hàng
                    let targetBin = '';
                    let bankNameRaw = order.user_bank_raw.bankName; // Lấy tên ngân hàng từ dữ liệu raw

                    if (dynamicBinMap[bankNameRaw]) {
                        targetBin = dynamicBinMap[bankNameRaw];
                    } else {
                        // 2. Tìm gần đúng (Fallback)
                        for (const [name, bin] of Object.entries(dynamicBinMap)) {
                            if (bankNameRaw.includes(name) || name.includes(bankNameRaw)) {
                                targetBin = bin;
                                break;
                            }
                        }
                    }

                    // 2. Nếu có BIN, tạo link QR VietQR
                    if (targetBin) {
                        const qrUrl = `https://img.vietqr.io/image/${targetBin}-${order.user_bank_raw.accountNo}-compact.jpg?amount=${order.user_bank_raw.amount}&addInfo=${encodeURIComponent(order.user_bank_raw.addInfo)}&accountName=${encodeURIComponent(order.user_bank_raw.accountName)}`;
                        qrBtn = `<a href="${qrUrl}" target="_blank" class="btn btn-xs btn-success" style="margin-top:5px;"><i class="fa fa-qrcode"></i> Quét QR Trả Tiền</a>`;
                    } else {
                        qrBtn = `<br><small style="color:red;">(Không tìm thấy mã BIN)</small>`;
                    }
                }

                const row = `
                <tr id="order-${order.id}">
                    <td><a href="checkout_payment_sell.html?id=${order.id}" target="_blank"><strong>${order.id}</strong></a></td>
                    <td>${escapeHTML(order.username)}</td>
                    <td>${numberFormat(order.amount_vnd, 0)} VNĐ</td>
                    <td>
                        ${order.detail_info} ${billLink}
                        <hr style="margin: 5px 0;">
                        <div style="background:#f9f9f9; padding:5px; border-radius:4px;">
                            <small style="color:#d9534f; font-weight:bold;">ND: ${order.sell_content}</small>
                            <br>${copyBtn} ${qrBtn}
                        </div>
                    </td> 
                    <td>${actionBtns}</td>
                </tr>`;
                sellTable.append(row);
                sellCount++;
            }
        });

        $('#stat-buy-pending').text(buyCount);
        $('#stat-sell-pending').text(sellCount);
        if (buyCount === 0) buyTable.append('<tr><td colspan="6" class="text-center">Không có đơn MUA nào đang chờ.</td></tr>');
        if (sellCount === 0) sellTable.append('<tr><td colspan="5" class="text-center">Không có đơn BÁN nào đang chờ.</td></tr>');
    }

    // --- Xử lý nút "Hoàn tất" ---
    $(document).on('click', '.btn-complete', function () {
        const btn = $(this); // [MỚI] Lưu lại nút đang bấm
        const orderId = btn.data('id');

        if (!confirm(`Bạn có chắc chắn muốn hoàn tất đơn hàng ${orderId} không?`)) {
            return;
        }

        setLoading(btn, true, 'Đang gửi...');

        $.ajax({
            // ... (các phần url, type giữ nguyên) ...
            url: `${API_URL}/api/admin/transactions/complete`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ order_id: orderId }),
            success: function (response) {
                if (response.success) {
                    alert(response.message);
                    btn.closest('tr').fadeOut(500, function () {
                        $(this).remove();
                        loadTransactions();
                    });
                }
            },
            error: function (xhr) {
                setLoading(btn, false);
                alert("Lỗi: " + xhr.responseJSON.message);
            }
        });
    });

    // --- Chạy lần đầu ---
    loadBinMap();
});