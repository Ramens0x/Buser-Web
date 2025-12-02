$(document).ready(function () {
    const draftOrder = JSON.parse(localStorage.getItem('draft_order'));

    if (!draftOrder) {
        alert("Lỗi: Không tìm thấy thông tin đơn hàng. Vui lòng thử lại.");
        window.location.href = "index.html";
        return;
    }

    // --- Hàm lấy Token (Cần thiết cho API) ---
    function getAuthToken() {
        const loginDataString = localStorage.getItem('buser_login_data');
        if (!loginDataString) return null;
        try {
            const loginData = JSON.parse(loginDataString);
            return loginData.token;
        } catch (e) { return null; }
    }

    const token = getAuthToken();
    if (!token) {
        window.location.href = "login.html";
        return;
    }

    // --- 1. Tải danh sách ngân hàng đã lưu ---
    $.ajax({
        url: `${API_URL}/api/user/banks`,
        type: 'GET',
        success: function (response) {
            const bankListDiv = $('.wallet-list');
            bankListDiv.empty(); // Xóa các bank tĩnh

            if (response.banks && response.banks.length > 0) {
                // [SỬA LỖI] Thay thế toàn bộ vòng lặp forEach:
                response.banks.forEach((bank, index) => {
                    // [FIX] Dọn dẹp TẤT CẢ dữ liệu trước khi sử dụng
                    let id = escapeHTML(bank.id);
                    let bank_name = escapeHTML(bank.bank_name);
                    let account_name = escapeHTML(bank.account_name);
                    let account_number = escapeHTML(bank.account_number);

                    const bankHtml = `
                    <div class="radio">
                    <label>
                    <input type="radio" name="bank_id" value="${id}" ${index === 0 ? 'checked' : ''}>
                    <strong>${bank_name} (${account_name})</strong>
                    <div class="wallet-details">
                    STK: ${account_number}
                    </div>
                    </label>
                    </div>`;
                    bankListDiv.append(bankHtml);
                });
            } else {
                bankListDiv.html("<p>Bạn chưa lưu tài khoản ngân hàng nào. Vui lòng thêm tài khoản mới.</p>");
            }
        },
        error: function (xhr) {
            alert("Lỗi khi tải danh sách ngân hàng: " + xhr.responseJSON.message);
        }
    });

    // --- 2. Xử lý nút "Xác nhận" (TẠO ĐƠN HÀNG) ---
    $('#select-bank-form').on('submit', function (e) {
        e.preventDefault();

        const selectedBankId = $('input[name="bank_id"]:checked').val();

        if (!selectedBankId) {
            alert("Vui lòng chọn một tài khoản ngân hàng để nhận, hoặc thêm tài khoản mới.");
            return;
        }

        const btn = $(this).find('button[type="submit"]');
        const originalText = btn.html();
        btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Đang xử lý...');

        // Gộp thông tin nháp + bank đã chọn
        var orderData = {
            ...draftOrder,
            bank_id: selectedBankId // Thêm ID bank đã chọn
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

                window.location.href = "checkout_payment_sell.html?id=" + response.order.id;
            },
            error: function (xhr) {
                alert("Lỗi khi tạo đơn hàng: " + xhr.responseJSON.message);
                btn.prop('disabled', false).html(originalText);
            }
        });
    });

});