$(document).ready(function () {

    // Ví dụ: reset-password.html?token=abc123xyz
    function getTokenFromUrl() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('token');
    }

    const resetToken = getTokenFromUrl();

    // Nếu không có token, báo lỗi
    if (!resetToken) {
        alert("Lỗi: Link đặt lại mật khẩu không hợp lệ.");
        $('#reset-password-form').hide();
    }

    // --- XỬ LÝ FORM ĐẶT LẠI MẬT KHẨU ---
    $('#reset-password-form').on('submit', function (e) {
        e.preventDefault();

        let newPass = $(this).find('input[name="new_password"]').val();
        let confirmPass = $(this).find('input[name="confirm_password"]').val();

        if (newPass !== confirmPass) {
            alert("Lỗi: Mật khẩu mới không khớp!");
            return;
        }

        var data = {
            token: resetToken,
            new_password: newPass
        };

        // Gửi đến API backend
        $.ajax({
            url: API_URL + "/api/reset-password",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function (response) {
                alert(response.message); // "Đặt lại mật khẩu thành công!"
                window.location.href = "login.html"; // Chuyển về trang đăng nhập
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message); // "Token không hợp lệ hoặc đã hết hạn"
            }
        });
    });

});