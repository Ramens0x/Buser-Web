$(document).ready(function () {
    const draftOrder = JSON.parse(localStorage.getItem('draft_order'));

    if (!draftOrder) {
        alert("Lỗi: Không tìm thấy thông tin đơn hàng. Vui lòng thử lại.");
        window.location.href = "index.html";
        return;
    }

    // Cập nhật Tiêu đề
    let coinName = draftOrder.coin === 'bustabit' ? 'Bustabit (BTC)' : 'USDT (BEP20)';
    $('.panel-heading h4').html(`<i class="fa fa-credit-card"></i> Chọn tài khoản ${coinName} để nhận`);

    // --- 1. Tải danh sách ví đã lưu ---
    $.ajax({
        url: `${API_URL}/api/user/wallets?coin_type=${draftOrder.coin}`,
        type: 'GET',
      
        success: function (response) {
            const walletListDiv = $('.wallet-list');
            walletListDiv.empty();

            if (response.wallets && response.wallets.length > 0) {
                // [SỬA LỖI] Thay thế toàn bộ vòng lặp forEach:
                response.wallets.forEach((wallet, index) => {
                    // [FIX] Dọn dẹp TẤT CẢ dữ liệu trước khi sử dụng
                    let id = escapeHTML(wallet.id);
                    let address = escapeHTML(wallet.address);
                    let name = escapeHTML(wallet.name);
                    let tag = escapeHTML(wallet.tag) || 'Không có';

                    let details = `ID: ${address}`;
                    if (wallet.coin_type === 'bustabit') {
                        details += ` | Tag: ${tag} | Tên: ${name}`;
                    }

                    const walletHtml = `
                    <div class="radio">
                    <label>
                    <input type="radio" name="wallet_id" value="${id}" ${index === 0 ? 'checked' : ''}>
                    <strong>${name || address.substring(0, 15) + '...'}</strong>
                    <div class="wallet-details">${details}</div>
                    </label>
                    </div>`;
                    walletListDiv.append(walletHtml);
                });
            } else {
                walletListDiv.html("<p>Bạn chưa lưu tài khoản nào. Vui lòng thêm tài khoản mới.</p>");
            }
        },
        error: function (xhr) {
            alert("Lỗi khi tải danh sách ví: " + xhr.responseJSON.message);
        }
    });

    // --- 2. Xử lý nút "Xác nhận" (TẠO ĐƠN HÀNG) ---
    $('#select-wallet-form').on('submit', function (e) {
        e.preventDefault();

        const selectedWalletId = $('input[name="wallet_id"]:checked').val();

        if (!selectedWalletId) {
            alert("Vui lòng chọn một ví để nhận, hoặc thêm một ví mới.");
            return;
        }

        const btn = $(this).find('button[type="submit"]');
        const originalText = btn.html();
        btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Đang xử lý...');

        // Gộp thông tin nháp + ví đã chọn
        var orderData = {
            ...draftOrder,
            wallet_id: selectedWalletId 
        };

        // Gọi API Tạo Đơn hàng
        $.ajax({
            url: API_URL + "/api/create-order",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(orderData),
          
            success: function (response) {
                localStorage.setItem('current_order', JSON.stringify(response.order));
                localStorage.removeItem('draft_order');
                window.location.href = "checkout_payment_buy.html?id=" + response.order.id;
            },
            error: function (xhr) {
                alert("Lỗi khi tạo đơn hàng: " + xhr.responseJSON.message);
                btn.prop('disabled', false).html(originalText);
            }
        });
    });

});