$(document).ready(function () {
    function getAuthToken() {
        const loginDataString = localStorage.getItem('buser_login_data');
        if (!loginDataString) return null;
        try { return JSON.parse(loginDataString).token; } catch (e) { return null; }
    }

    const token = getAuthToken();
    if (!token) { window.location.href = "login.html"; return; }

    // 1. Lấy ID từ URL (Ví dụ: checkout_payment_buy.html?id=BUSER123)
    const urlParams = new URLSearchParams(window.location.search);
    const orderId = urlParams.get('id');

    if (!orderId) {
        alert("Thiếu mã đơn hàng!");
        window.location.href = "index.html";
        return;
    }

    // 2. Gọi API lấy chi tiết đơn hàng
    $.ajax({
        url: `${API_URL}/api/order/${orderId}`,
        type: 'GET',
        beforeSend: function (xhr) { xhr.setRequestHeader('Authorization', 'Bearer ' + token); },
        success: function (response) {
            if (response.success) {
                renderOrderData(response.order);
                setupLiveUpdate(response.order.id); // Kích hoạt Live Update
            }
        },
        error: function (xhr) {
            alert("Lỗi: " + (xhr.responseJSON ? xhr.responseJSON.message : "Không thể tải đơn hàng"));
            window.location.href = "index.html";
        }
    });

    function renderOrderData(order) {
        // Hiển thị thông tin cơ bản
        $('#order-id').text(escapeHTML(order.id));
        $('#order-time').text(new Date(order.created_at).toLocaleString('vi-VN'));

        $('#upload-order-id').val(order.id);

        // Hiển thị thông tin thanh toán (Admin nhận tiền)
        const info = order.payment_info;
        if (info) {
            $('#payment-bank').text(info.bank);
            $('#payment-account-number').text(escapeHTML(info.account_number));
            $('#payment-account-name').text(escapeHTML(info.account_name));
            $('#payment-amount').text(numberFormat(info.amount, 0) + ' VNĐ');
            $('#payment-content').text(escapeHTML(info.content));

            // Hiển thị QR
            const qrData = encodeURIComponent(order.qr_data_string);
            const qrImgSrc = `${API_URL}/api/generate-qr?data=${qrData}`;
            $('#qr-image').attr('src', qrImgSrc);
        }

        // Hiển thị thông tin nhận Coin (User)
        $('#confirm-coin-type').text(order.coin.toUpperCase());
        $('#confirm-coin-amount').text(numberFormat(order.amount_coin, 8));

        // Lấy chi tiết ví user để hiển thị
        $.ajax({
            url: `${API_URL}/api/user/wallets?coin_type=${order.coin}`,
            type: 'GET',
            beforeSend: function (xhr) { xhr.setRequestHeader('Authorization', 'Bearer ' + token); },
            success: function (res) {
                const selectedWallet = res.wallets.find(w => w.id === order.user_wallet_id);
                if (selectedWallet) {
                    $('#confirmation-wallet-details').remove();
                    let detailsHtml = `<li id="confirmation-wallet-details"><strong>Địa chỉ ví:</strong> <span style="color: #333;">${escapeHTML(selectedWallet.address)}</span></li>`;
                    if (order.coin === 'bustabit') {
                        detailsHtml += `<li><strong>Tag:</strong> <span style="color: #333;">${escapeHTML(selectedWallet.tag) || 'Không có'}</span></li>
                                        <li><strong>Tên:</strong> <span style="color: #333;">${escapeHTML(selectedWallet.name)}</span></li>`;
                    }
                    $('#confirm-coin-amount').closest('li').after(detailsHtml);
                }
            }
        });

        // Xử lý nút Hủy
        if (order.status !== 'pending') {
            $('#btn-user-cancel').prop('disabled', true).text(order.status === 'completed' ? 'Đã Hoàn Thành' : 'Đã Hủy');
            $('.payment-box').css('opacity', '0.7');
            if (order.status === 'completed') {
                $('.confirmation-box').append('<div class="alert alert-success" style="margin-top: 15px;"><strong><i class="fa fa-check-circle"></i> GIAO DỊCH THÀNH CÔNG!</strong></div>');
            }
        }

        // Gán sự kiện click nút Hủy
        $('#btn-user-cancel').off('click').on('click', function () {
            if (!confirm('Bạn có chắc chắn muốn HỦY đơn hàng này không?')) return;
            $.ajax({
                url: `${API_URL}/api/user/cancel-order`,
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ order_id: order.id }),
                beforeSend: function (xhr) { xhr.setRequestHeader('Authorization', 'Bearer ' + token); },
                success: function (res) {
                    alert(res.message);
                    location.reload(); // Tải lại trang để cập nhật trạng thái
                }
            });
        });
    }

    // Hàm Live Update (đã tích hợp vào đây)
    function setupLiveUpdate(orderId) {
        const socket = io(API_URL);
        socket.emit('join_room', { room_id: orderId });
        socket.on('order_completed', function (data) {
            if (data.order_id === orderId) {
                alert('Đơn hàng của bạn đã được hoàn tất!');
                location.reload(); // Tải lại trang để hiện trạng thái mới
            }
        });
    }

    // --- XỬ LÝ UPLOAD BILL ---
    $('#upload-bill-form').on('submit', function (e) {
        e.preventDefault();

        // Kiểm tra xem có orderId chưa (lấy từ URL ở đầu file)
        if (!orderId) {
            alert("Lỗi: Không tìm thấy mã đơn hàng!");
            return;
        }

        const formData = new FormData(this);
        //formData.append('order_id', orderId);

        // Hiển thị trạng thái đang tải
        const btn = $(this).find('button[type="submit"]');
        const originalText = btn.html();
        btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Đang tải...');

        $.ajax({
            url: `${API_URL}/api/upload-bill`,
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            beforeSend: function (xhr) {
                xhr.setRequestHeader('Authorization', 'Bearer ' + token);
            },
            success: function (res) {
                alert(res.message);
                $('#upload-bill-form').parent().removeClass('alert-info').addClass('alert-success')
                    .html('<strong><i class="fa fa-check"></i> Đã gửi ảnh chứng từ thành công!</strong> Admin đang kiểm tra.');
            },
            error: function (xhr) {
                alert('❌ Lỗi: ' + (xhr.responseJSON ? xhr.responseJSON.message : "Không thể tải ảnh"));
                btn.prop('disabled', false).html(originalText); // Mở lại nút nếu lỗi
            }
        });
    });
});