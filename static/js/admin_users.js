$(document).ready(function () {
    let currentPage = 1;
    let totalPages = 1;

    function loadUsers(page = 1) {
        $('#users-table-body').html('<tr><td colspan="6" class="text-center"><i class="fa fa-spinner fa-spin"></i> Đang tải...</td></tr>');
        
        $.ajax({
            url: `${API_URL}/api/admin/users`, 
            type: 'GET',
            data: { page: page }, // Gửi tham số page
            success: function (res) {
                if (res.success) {
                    renderUsersTable(res.users);
                    
                    // Cập nhật phân trang
                    if (res.pagination) {
                        currentPage = res.pagination.current_page;
                        totalPages = res.pagination.total_pages;
                        $('#page-display').text(currentPage);
                        $('#total-pages').text(totalPages);
                        
                        // Xử lý nút bấm
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

    function renderUsersTable(users) {
        const tableBody = $('#users-table-body');
        tableBody.empty();

        if (users.length === 0) {
            tableBody.append('<tr><td colspan="6" class="text-center">Không có dữ liệu.</td></tr>');
            return;
        }

        users.forEach(user => {
            const row = `
                <tr id="user-${user.id}">
                    <td>${escapeHTML(user.id)}</td>
                    <td><strong>${escapeHTML(user.username)}</strong></td>
                    <td>${escapeHTML(user.email)}</td>
                    <td>${escapeHTML(user.role)}</td>
                    <td>${user.order_count}</td>
                    <td>
                        <button class="btn btn-xs btn-warning btn-edit" data-id="${user.id}">Sửa</button>
                        <button class="btn btn-xs btn-danger btn-ban" data-id="${user.id}">Cấm</button>
                    </td>
                </tr>`;
            tableBody.append(row);
        });
    }

    // Sự kiện nút bấm
    $('#btn-prev-users').click(function(e) {
        e.preventDefault();
        if (currentPage > 1) loadUsers(currentPage - 1);
    });

    $('#btn-next-users').click(function(e) {
        e.preventDefault();
        if (currentPage < totalPages) loadUsers(currentPage + 1);
    });

    loadUsers(1);
});