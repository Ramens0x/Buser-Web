$(document).ready(function () {

    // --- Tải dữ liệu Người dùng ---
    function loadUsers() {
        $.ajax({
            url: `${API_URL}/api/admin/users`, 
            type: 'GET',
            success: function (response) {
                if (response.success) {
                    renderUsersTable(response.users);
                }
            },
            error: function (xhr) {
                alert("Lỗi tải danh sách: " + xhr.responseJSON.message);
                window.location.href = "index.html";
            }
        });
    }

    // --- Hiển thị dữ liệu lên bảng ---
    function renderUsersTable(users) {
        const tableBody = $('#users-table-body');
        tableBody.empty();

        if (users.length === 0) {
            tableBody.append('<tr><td colspan="6" class="text-center">Không có người dùng nào (ngoài bạn).</td></tr>');
            return;
        }

        users.forEach(user => {
            const row = `
                <tr id="user-${user.id}">
                    <td>${escapeHTML(user.id)}</td>
                    <td><strong>${escapeHTML(user.username)}</strong></td>
                    <td>${escapeHTML(user.email)}</td>
                    <td>${escapeHTML(user.role)}</td>
                    <td>
                        <button class="btn btn-xs btn-warning btn-edit" data-id="${user.id}">Sửa</button>
                        <button class="btn btn-xs btn-danger btn-ban" data-id="${user.id}">Cấm</button>
                    </td>
                </tr>`;
            tableBody.append(row);
        });
    }

    // --- Chạy lần đầu ---
    loadUsers();
});