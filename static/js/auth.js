$(document).ready(function () {

    // --- 1. HÀM BẢO VỆ TRANG ADMIN (SECURITY GUARD) ---
    // Hàm này sẽ chạy ngay khi trang tải xong để kiểm tra quyền truy cập
    function protectAdminPages(user) {
        const path = window.location.pathname;

        // Chỉ kiểm tra nếu đang đứng ở các trang Admin (có chữ 'admin_')
        if (path.includes('admin_')) {

            // TRƯỜNG HỢP 1: Chưa đăng nhập -> Đá về Login
            if (!user) {
                alert("Vui lòng đăng nhập để truy cập trang Quản trị!");
                window.location.href = 'login.html';
                return false; // Dừng lại
            }

            // TRƯỜNG HỢP 2: Là User thường -> Đá về Trang chủ
            if (user.role === 'User') {
                alert("⛔ Bạn không có quyền truy cập trang này!");
                window.location.href = 'index.html';
                return false;
            }

            // TRƯỜNG HỢP 3: Là Manager -> Chặn các trang nhạy cảm cụ thể
            if (user.role === 'Manager') {
                // Danh sách các file CẤM Manager truy cập
                const forbiddenPages = [
                    'admin_users.html',             // Cấm quản lý user
                    'admin_spread.html',            // Cấm chỉnh giá
                    'admin_settings.html',          // Cấm cài Bank/Ví
                    'admin_settings_fee.html',      // Cấm chỉnh Bảng Phí HTML
                    'admin_settings_buy_fee.html',  // Cấm chỉnh Phí Mua
                    'admin_settings_telegram.html'  // Cấm chỉnh Telegram
                    // LƯU Ý: Không cấm 'admin_settings_internal.html' (Coin nội bộ)
                ];

                // Kiểm tra xem link hiện tại có nằm trong danh sách cấm không
                for (let page of forbiddenPages) {
                    if (path.includes(page)) {
                        alert('⛔ Bạn không có quyền truy cập mục này (Chỉ dành cho Admin).');
                        window.location.href = 'admin_dashboard.html'; // Đá về dashboard quản lý
                        return false;
                    }
                }
            }
        }
        return true; // Cho phép đi tiếp
    }

    // --- 2. QUẢN LÝ GIAO DIỆN (UI) ---
    function checkLoginState() {
        const userDataString = localStorage.getItem('buser_user');
        let user = null;

        if (userDataString) {
            user = JSON.parse(userDataString);
        }

        // === GỌI HÀM BẢO VỆ NGAY TẠI ĐÂY ===
        // Nếu hàm bảo vệ trả về false (bị đá) thì không chạy tiếp code bên dưới nữa
        if (!protectAdminPages(user)) return;

        if (user) {
            // --- ĐÃ ĐĂNG NHẬP ---
            $('#menu-register, #menu-login').hide();
            $('#menu-profile, #menu-logout').show();

            if ($('#sidebar-username').length > 0) {
                $('#sidebar-username').text(user.username);
            }

            // Nút Quản trị: Chỉ hiện cho Admin và Manager
            if (user.role === 'Admin' || user.role === 'Manager') {
                $('#menu-admin').show();
            } else {
                $('#menu-admin').hide();
            }

            $('#btn-submit-swap').text('Tiếp tục').removeClass('btn-primary').addClass('btn-success');

            // --- XỬ LÝ MENU BÊN TRÁI CHO MANAGER ---
            if (user.role === 'Manager') {
                // Ẩn các menu con cụ thể (Dựa vào href)
                $('a[href="admin_users.html"]').parent().hide();            // Ẩn Quản lý User
                $('a[href="admin_spread.html"]').parent().hide();           // Ẩn Quản lý Giá

                // Ẩn các mục Cài đặt cấm (Giữ lại Coin Nội Bộ)
                $('a[href="admin_settings.html"]').parent().hide();         // Ẩn Ngân hàng
                $('a[href="admin_settings_fee.html"]').parent().hide();     // Ẩn Bảng phí
                $('a[href="admin_settings_buy_fee.html"]').parent().hide(); // Ẩn Phí mua
                $('a[href="admin_settings_telegram.html"]').parent().hide();// Ẩn Telegram
            }

        } else {
            // --- CHƯA ĐĂNG NHẬP ---
            $('#menu-register, #menu-login').show();
            $('#menu-profile, #menu-admin, #menu-logout').hide();
            $('#btn-submit-swap').text('Đăng Nhập / Đăng Ký').removeClass('btn-success').addClass('btn-primary');
        }
    }

    // Khởi chạy logic
    checkLoginState();

    // --- 3. CÁC LOGIC KHÁC (Logout, Login, Register...) ---

    function isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    $('#btn-logout').on('click', function (e) {
        e.preventDefault();
        if (!confirm("Bạn có chắc muốn đăng xuất?")) return;
        localStorage.removeItem('buser_user');
        $.ajax({
            url: API_URL + "/api/logout", type: 'POST',
            success: function () { window.location.href = "index.html"; },
            error: function () { window.location.href = "index.html"; }
        });
    });

    $("#login-form").on('submit', function (e) {
        e.preventDefault();
        var data = {
            username: $(this).find('input[name="username"]').val(),
            password: $(this).find('input[name="password"]').val()
        };
        // Hiệu ứng loading nút
        const btn = $(this).find('button');
        const oldText = btn.html();
        setLoading(btn, true, 'Đang đăng nhập...');

        $.ajax({
            url: API_URL + "/api/login",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function (response) {
                alert(response.message);
                localStorage.setItem('buser_user', JSON.stringify(response.user));

                // Chuyển hướng thông minh
                if (response.user.role === 'Admin' || response.user.role === 'Manager') {
                    window.location.href = "admin_dashboard.html";
                } else {
                    window.location.href = "index.html";
                }
            },
            error: function (xhr) {
                setLoading(btn, false, oldText);
                alert("Lỗi: " + (xhr.responseJSON ? xhr.responseJSON.message : "Đăng nhập thất bại"));
            }
        });
    });

    $("#register-form").on('submit', function (e) {
        e.preventDefault();
        const email = $(this).find('input[name="email"]').val();
        if (!isValidEmail(email)) { alert("Email không hợp lệ!"); return; }

        var data = {
            username: $(this).find('input[name="username"]').val(),
            email: email,
            password: $(this).find('input[name="password"]').val()
        };

        const btn = $(this).find('button');
        const oldText = btn.html();
        setLoading(btn, true, 'Đang đăng ký...');

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
                setLoading(btn, false, oldText);
                alert("Lỗi: " + (xhr.responseJSON ? xhr.responseJSON.message : "Đăng ký thất bại"));
            }
        });
    });

    $('#forgot-password-form').on('submit', function (e) {
        e.preventDefault();
        var data = { email: $(this).find('input[type="email"]').val() };

        const btn = $(this).find('button');
        const oldText = btn.html();
        setLoading(btn, true, 'Đang gửi...');

        $.ajax({
            url: API_URL + "/api/forgot-password",
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function (response) {
                alert(response.message);
                $('#forgot-password-form')[0].reset();
                setLoading(btn, false, oldText);
            },
            error: function (xhr) {
                setLoading(btn, false, oldText);
                alert("Lỗi: " + (xhr.responseJSON ? xhr.responseJSON.message : "Có lỗi xảy ra"));
            }
        });
    });
});