$(document).ready(function () {
    const urlParams = new URLSearchParams(window.location.search);
    const orderId = urlParams.get('id');

    if (!orderId) {
        alert("Lỗi: Không tìm thấy mã đơn hàng!");
        window.location.href = "index.html";
        return;
    }
    // 2. Gọi API lấy chi tiết đơn hàng
    $.ajax({
        url: `${API_URL}/api/order/${orderId}`,
        type: 'GET',
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
        // --- 1. HIỂN THỊ THÔNG TIN CƠ BẢN ---
        $('#order-id').text(escapeHTML(order.id));
        $('#order-time').text(new Date(order.created_at).toLocaleString('vi-VN'));

        $('#upload-order-id').val(order.id);

        const info = order.payment_info || {};

        $('#payment-bank').text(info.bank_name || info.bank || 'Chưa cập nhật');
        $('#payment-account-number').text(escapeHTML(info.account_number || '...'));
        $('#payment-account-name').text(escapeHTML(info.account_name || '...'));
        $('#payment-amount').text(numberFormat(info.amount || order.amount_vnd, 0) + ' VNĐ');
        $('#payment-content').text(escapeHTML(info.content || '...'));

        if (order.qr_data_string) {
            const qrData = encodeURIComponent(order.qr_data_string);
            const qrImgSrc = `${API_URL}/api/generate-qr?data=${qrData}`;
            $('#qr-image').attr('src', qrImgSrc).show();
        } else {
            $('#qr-image').hide();
            $('#qr-image').parent().html('<p class="text-danger text-center">Không thể tạo QR</p>');
        }

        $('#confirm-coin-type').text(order.coin.toUpperCase());
        $('#confirm-coin-amount').text(numberFormat(order.amount_coin, 8));

        // Lấy thông tin ví (bổ sung)
        $.ajax({
            url: `${API_URL}/api/user/wallets?coin_type=${order.coin}`,
            type: 'GET',
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

        // --- 2. XỬ LÝ THANH TRẠNG THÁI (STEPPER) & NÚT BẤM ---
        if (order.status === 'completed') {
            // A. Cập nhật Stepper (Thanh tiến trình)
            // Bước 2: Đổi thành dấu tích xanh
            $('.stepper .step:eq(1)').removeClass('active');
            $('.stepper .step:eq(1) .circle').html('<i class="fa fa-check"></i>')
                .css({'background-color': '#28a745', 'color': 'white', 'border-color': '#28a745'});
            
            // Bước 3: Kích hoạt (Active)
            $('.stepper .step:eq(2)').addClass('active');
            $('.stepper .step:eq(2) .circle').css('background-color', '#28a745'); // Tô xanh số 3
            
            // B. Cập nhật nút bấm (Thay đổi giao diện nút Hủy thành nút Thành công)
            $('#btn-user-cancel')
                .removeClass('btn-default btn-danger')
                .addClass('btn-success')
                .html('<i class="fa fa-check-circle"></i> Giao Dịch Thành Công')
                .prop('disabled', true)
                .css('opacity', '1'); 
            
            // Hiển thị thêm thông báo text
            if ($('.alert-success-msg').length === 0) {
                $('.confirmation-box').append('<div class="alert alert-success alert-success-msg" style="margin-top: 15px;"><strong><i class="fa fa-check-circle"></i> GIAO DỊCH THÀNH CÔNG!</strong></div>');
            }

        } else if (order.status === 'cancelled') {
             // Nếu đơn hủy: Nút chuyển màu đỏ
             $('#btn-user-cancel')
                .removeClass('btn-default')
                .addClass('btn-danger')
                .html('<i class="fa fa-times-circle"></i> Đơn Đã Hủy')
                .prop('disabled', true);
             
             $('.auth-box').css('opacity', '0.6'); // Làm mờ khung thanh toán
        }

        // --- 3. GÁN SỰ KIỆN CLICK NÚT HỦY ---
        $('#btn-user-cancel').off('click').on('click', function () {
            if ($(this).prop('disabled')) return; // Chặn nếu nút đang disable
            
            if (!confirm('Bạn có chắc chắn muốn HỦY đơn hàng này không?')) return;
            
            $.ajax({
                url: `${API_URL}/api/user/cancel-order`,
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ order_id: order.id }),
                success: function (res) {
                    alert(res.message);
                    location.reload(); 
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