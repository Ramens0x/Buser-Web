$(document).ready(function () {
    const urlParams = new URLSearchParams(window.location.search);
    const orderId = urlParams.get('id');

    if (!orderId) {
        alert("Lỗi: Không tìm thấy mã đơn hàng!");
        window.location.href = "index.html";
        return;
    }

    $.ajax({
        url: `${API_URL}/api/order/${orderId}`,
        type: 'GET',
        success: function (response) {
            if (response.success) {
                renderOrderData(response.order);
                setupLiveUpdate(response.order.id);
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

        // [QUAN TRỌNG] Gán ID vào form upload để gửi đi
        $('#upload-order-id').val(order.id);

        const info = order.payment_info;
        if (info) {
            $('#sell-amount').text(numberFormat(order.amount_coin, 8));
            $('#sell-coin-type').text(order.coin.toUpperCase());
            $('#admin-wallet-network').text(info.network);
            $('#admin-wallet-address').text(escapeHTML(info.wallet_address));

            if (info.memo) {
                $('#admin-wallet-memo-li').show();
                $('#admin-wallet-memo').text(escapeHTML(info.memo));
            } else {
                $('#admin-wallet-memo-li').hide();
            }
        }

        $('#receive-amount-vnd').text(numberFormat(order.amount_vnd, 0));

        // Xử lý hiển thị thông tin ngân hàng nhận tiền
        if (order.payment_info && order.payment_info.user_bank_snapshot && order.payment_info.user_bank_snapshot.bank_name) {
            const bankSnap = order.payment_info.user_bank_snapshot;
            $('#user-bank-name').text(escapeHTML(bankSnap.bank_name));
            $('#user-bank-account').text(escapeHTML(bankSnap.account_number));
            $('#user-account-name').text(escapeHTML(bankSnap.account_name));
        } else {
            // Fallback
            $.ajax({
                url: `${API_URL}/api/user/banks`,
                type: 'GET',
                success: function (res) {
                    const selectedBank = res.banks.find(b => b.id === order.user_bank_id);
                    if (selectedBank) {
                        $('#user-bank-name').text(escapeHTML(selectedBank.bank_name));
                        $('#user-bank-account').text(escapeHTML(selectedBank.account_number));
                        $('#user-account-name').text(escapeHTML(selectedBank.account_name));
                    } else {
                        $('#user-bank-name').text("Không tìm thấy (Đã xóa)");
                    }
                }
            });
        }

        if (order.payment_info && order.payment_info.sell_content) {
            $('#sell-order-content').text(order.payment_info.sell_content);
        } else {
            $('#sell-order-content').text(`${order.id} HOANG NGOC SON transfer`);
        }

        // --- 2. XỬ LÝ THANH TRẠNG THÁI (STEPPER) & NÚT BẤM ---
        if (order.status === 'completed') {
            // A. Cập nhật Stepper
            $('.stepper .step:eq(1)').removeClass('active');
            $('.stepper .step:eq(1) .circle').html('<i class="fa fa-check"></i>')
                .css({ 'background-color': '#28a745', 'color': 'white', 'border-color': '#28a745' });

            $('.stepper .step:eq(2)').addClass('active');
            $('.stepper .step:eq(2) .circle').css('background-color', '#28a745');

            // B. Cập nhật nút bấm
            $('#btn-user-cancel')
                .removeClass('btn-default btn-danger')
                .addClass('btn-success')
                .html('<i class="fa fa-check-circle"></i> Giao Dịch Thành Công')
                .prop('disabled', true)
                .css('opacity', '1');

            if ($('.alert-success-msg').length === 0) {
                $('.auth-box').append('<div class="alert alert-success alert-success-msg text-center" style="margin: 20px;"><strong><i class="fa fa-check-circle"></i> GIAO DỊCH THÀNH CÔNG!</strong></div>');
            }

            // Khóa form upload nếu đã hoàn thành
            $('#upload-bill-form button').prop('disabled', true).text('Đã hoàn tất');

        } else if (order.status === 'cancelled') {
            $('#btn-user-cancel')
                .removeClass('btn-default')
                .addClass('btn-danger')
                .html('<i class="fa fa-times-circle"></i> Đơn Đã Hủy')
                .prop('disabled', true);

            $('.auth-box').css('opacity', '0.6');
            $('#upload-bill-form button').prop('disabled', true);
        }

        // --- 3. GÁN SỰ KIỆN CLICK NÚT HỦY ---
        $('#btn-user-cancel').off('click').on('click', function () {
            if ($(this).prop('disabled')) return;
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

    // Hàm Live Update: Tự động chuyển trang khi hoàn tất
    function setupLiveUpdate(orderId) {
        const socket = io(API_URL);

        // Tham gia room
        socket.emit('join_room', { room_id: orderId });
        console.log("Đã kết nối Socket bán, đang theo dõi: " + orderId);

        // 1. Xử lý khi Admin xác nhận đã chuyển tiền (Hoàn tất)
        socket.on('order_completed', function (data) {
            if (data.order_id === orderId) {
                console.log("Giao dịch hoàn tất! Chuyển trang...");
                window.location.href = "/transaction/" + orderId;
            }
        });

        // 2. Xử lý khi đơn bị hủy
        socket.on('order_cancelled', function (data) {
            if (data.order_id === orderId) {
                console.log("Giao dịch bị hủy! Chuyển trang...");
                window.location.href = "/transaction/" + orderId;
            }
        });
    }

    // Xử lý Upload Bill
    $('#upload-bill-form').on('submit', function (e) {
        e.preventDefault();

        if (!orderId) {
            alert("Lỗi: Không tìm thấy mã đơn hàng!");
            return;
        }

        const formData = new FormData(this);
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
                    .html('<strong><i class="fa fa-check"></i> Đã gửi ảnh xác nhận thành công!</strong> Admin đang kiểm tra ví.');
            },
            error: function (xhr) {
                alert('❌ Lỗi: ' + (xhr.responseJSON ? xhr.responseJSON.message : "Không thể tải ảnh"));
                btn.prop('disabled', false).html(originalText);
            }
        });
    });
});