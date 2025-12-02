$(document).ready(function () {
    function getAuthToken() {
        const loginDataString = localStorage.getItem('buser_login_data');
        if (!loginDataString) return null;
        try { return JSON.parse(loginDataString).token; } catch (e) { return null; }
    }

    const token = getAuthToken();
    if (!token) { window.location.href = "login.html"; return; }

    const urlParams = new URLSearchParams(window.location.search);
    const orderId = urlParams.get('id');

    if (!orderId) {
        alert("Thiếu mã đơn hàng!");
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
        $('#order-id').text(escapeHTML(order.id));
        $('#order-time').text(new Date(order.created_at).toLocaleString('vi-VN'));

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
        $.ajax({
            url: `${API_URL}/api/user/banks`,
            type: 'GET',
         
            success: function (res) {
                const selectedBank = res.banks.find(b => b.id === order.user_bank_id);
                if (selectedBank) {
                    $('#user-bank-name').text(escapeHTML(selectedBank.bank_name));
                    $('#user-bank-account').text(escapeHTML(selectedBank.account_number));
                    
                    $('#user-account-name').text(escapeHTML(selectedBank.account_name));
                }
            }
        });
        if (order.payment_info && order.payment_info.sell_content) {
            $('#sell-order-content').text(order.payment_info.sell_content);
        } else {
            // Fallback cho đơn cũ
            $('#sell-order-content').text(`${order.id} HOANG NGOC SON transfer`);
        }

        if (order.status !== 'pending') {
            $('#btn-user-cancel').prop('disabled', true).text(order.status === 'completed' ? 'Đã Hoàn Thành' : 'Đã Hủy');
            $('.payment-box').css('opacity', '0.7');
            if (order.status === 'completed') {
                $('.confirmation-box').append('<div class="alert alert-success" style="margin-top: 15px;"><strong><i class="fa fa-check-circle"></i> GIAO DỊCH THÀNH CÔNG!</strong></div>');
            }
        }

        $('#btn-user-cancel').off('click').on('click', function () {
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

    function setupLiveUpdate(orderId) {
        const socket = io(API_URL);
        socket.emit('join_room', { room_id: orderId });
        socket.on('order_completed', function (data) {
            if (data.order_id === orderId) {
                alert('Đơn hàng của bạn đã được hoàn tất!');
                location.reload();
            }
        });
    }
});