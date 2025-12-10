$(document).ready(function () {
    let currentPage = 1;
    let totalPages = 1;

    // --- Hàm tải danh sách User ---
    function loadUsers(page = 1) {
        $('#users-table-body').html('<tr><td colspan="6" class="text-center"><i class="fa fa-spinner fa-spin"></i> Đang tải...</td></tr>');

        $.ajax({
            url: `${API_URL}/api/admin/users`,
            type: 'GET',
            data: { page: page },
            success: function (res) {
                if (res.success) {
                    renderUsersTable(res.users);

                    // Cập nhật phân trang
                    if (res.pagination) {
                        currentPage = res.pagination.current_page;
                        totalPages = res.pagination.total_pages;
                        $('#page-display').text(currentPage);
                        $('#total-pages').text(totalPages);

                        $('#btn-prev-users').parent().toggleClass('disabled', currentPage <= 1);
                        $('#btn-next-users').parent().toggleClass('disabled', currentPage >= totalPages);
                    }
                }
            },
            error: function (xhr) {
                alert("Lỗi tải danh sách: " + xhr.responseJSON.message);
            }
        });
    }

    // --- Hàm hiển thị bảng User (LOGIC MỚI) ---
    function renderUsersTable(users) {
        const tableBody = $('#users-table-body');
        tableBody.empty();

        if (users.length === 0) {
            tableBody.append('<tr><td colspan="6" class="text-center">Không có dữ liệu.</td></tr>');
            return;
        }

        users.forEach(user => {
            // 1. Tạo Badge hiển thị quyền
            let roleBadge = '';
            if (user.role === 'Admin') roleBadge = '<span class="label label-danger">Admin</span>';
            else if (user.role === 'Manager') roleBadge = '<span class="label label-primary">Manager</span>';
            else roleBadge = '<span class="label label-default">User</span>';

            // 2. Tạo nút bấm thay đổi quyền
            let actionBtns = '';

            // Nếu là User -> Hiện nút Thăng chức Manager
            if (user.role === 'User') {
                actionBtns += `<button class="btn btn-xs btn-primary btn-set-role" data-id="${user.id}" data-role="Manager" style="margin-right:5px;">Thăng Manager</button>`;
            }
            // Nếu là Manager -> Hiện nút Hạ chức về User
            else if (user.role === 'Manager') {
                actionBtns += `<button class="btn btn-xs btn-warning btn-set-role" data-id="${user.id}" data-role="User" style="margin-right:5px;">Hạ User</button>`;
            }

            // Nút Khóa tài khoản (Giữ nguyên)
            actionBtns += `<button class="btn btn-xs btn-danger btn-ban" data-id="${user.id}">Khóa</button>`;

            const row = `
                <tr id="user-${user.id}">
                    <td>${escapeHTML(user.id)}</td>
                    <td><strong>${escapeHTML(user.username)}</strong></td>
                    <td>${escapeHTML(user.email)}</td>
                    <td>${roleBadge}</td>
                    <td>${user.order_count}</td>
                    <td>${actionBtns}</td>
                </tr>`;
            tableBody.append(row);
        });
    }

    // --- Sự kiện click nút Đổi Quyền ---
    $(document).on('click', '.btn-set-role', function () {
        const userId = $(this).data('id');
        const newRole = $(this).data('role'); // Manager hoặc User

        if (!confirm(`Xác nhận thay đổi quyền của user này thành ${newRole}?`)) return;

        // Gọi API Admin
        $.ajax({
            url: `${API_URL}/api/admin/update-role`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ user_id: userId, new_role: newRole }),
            success: function (res) {
                alert(res.message);
                loadUsers(currentPage); // Tải lại danh sách
            },
            error: function (xhr) {
                alert("Lỗi: " + (xhr.responseJSON ? xhr.responseJSON.message : "Không thể thực hiện"));
            }
        });
    });

    // Các sự kiện phân trang
    $('#btn-prev-users').click(function (e) {
        e.preventDefault();
        if (currentPage > 1) loadUsers(currentPage - 1);
    });

    $('#btn-next-users').click(function (e) {
        e.preventDefault();
        if (currentPage < totalPages) loadUsers(currentPage + 1);
    });

    // Chạy lần đầu
    loadUsers(1);
});