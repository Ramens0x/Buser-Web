$(document).ready(function () {
    
    // Biến toàn cục quản lý phân trang
    let currentPage = 1;
    let totalPages = 1;

    // --- Hàm tải dữ liệu (Có kèm tham số lọc & phân trang) ---
    function loadHistory(page = 1) {
        // 1. Lấy dữ liệu từ các ô tìm kiếm bên HTML
        const userOrId = $('#filter-user').val(); // Đây chính là phần "username: user" bạn thắc mắc
        const coin = $('#filter-coin').val();
        const dFrom = $('#filter-date-from').val();
        const dTo = $('#filter-date-to').val();

        // Hiển thị loading (nếu muốn)
        $('#history-table-body').html('<tr><td colspan="7" class="text-center"><i class="fa fa-spinner fa-spin"></i> Đang tải dữ liệu...</td></tr>');

        $.ajax({
            url: `${API_URL}/api/admin/transactions/history`,
            type: 'GET',
            // Gửi các tham số này lên Backend
            data: { 
                page: page, 
                username: userOrId,  // Backend sẽ tìm cái này trong cả User và ID
                coin: coin, 
                date_from: dFrom, 
                date_to: dTo 
            },
            success: function (res) {
                if (res.success) {
                    renderHistoryTable(res.transactions);
                    
                    // Cập nhật giao diện Phân trang
                    if (res.pagination) {
                        currentPage = res.pagination.current_page;
                        totalPages = res.pagination.total_pages;
                        
                        $('#page-display').text(currentPage);
                        $('#total-pages').text(totalPages);
                        
                        // Ẩn/Hiện nút Trước/Sau
                        if (currentPage <= 1) $('#btn-prev-page').parent().addClass('disabled');
                        else $('#btn-prev-page').parent().removeClass('disabled');

                        if (currentPage >= totalPages) $('#btn-next-page').parent().addClass('disabled');
                        else $('#btn-next-page').parent().removeClass('disabled');
                    }
                }
            },
            error: function (xhr) {
                alert("Lỗi tải lịch sử: " + (xhr.responseJSON ? xhr.responseJSON.message : "Lỗi kết nối"));
            }
        });
    }

    // --- Hàm hiển thị bảng (Giữ nguyên logic hiển thị của bạn) ---
    function renderHistoryTable(transactions) {
        const tableBody = $('#history-table-body');
        tableBody.empty(); 

        if (!transactions || transactions.length === 0) {
            tableBody.append('<tr><td colspan="7" class="text-center">Không tìm thấy giao dịch nào.</td></tr>');
            return;
        }

        transactions.forEach(tx => {
            let linkPage = 'checkout_payment_buy.html'; 
            if (tx.mode === 'Bán' || tx.mode === 'sell') {
                linkPage = 'checkout_payment_sell.html';
            }

            const idLink = `<a href="${linkPage}?id=${escapeHTML(tx.id)}" target="_blank" style="font-weight: bold; text-decoration: underline;">${escapeHTML(tx.id)}</a>`;

            const row = `
                <tr>
                    <td>${idLink}</td> <td>${escapeHTML(tx.created_at)}</td>
                    <td>${escapeHTML(tx.username)}</td>
                    <td>${escapeHTML(tx.mode)}</td>
                    <td>${escapeHTML(tx.coin)}</td>
                    <td>${numberFormat(tx.amount_coin, 8)}</td>
                    <td>${numberFormat(tx.amount_vnd, 0)} VNĐ</td>
                </tr>`;
            tableBody.append(row);
        });
    }

    // --- CÁC SỰ KIỆN (EVENTS) ---

    // 1. Khi bấm nút "Tìm"
    $('#history-filter-form').on('submit', function(e) {
        e.preventDefault();
        loadHistory(1); // Luôn quay về trang 1 khi tìm kiếm mới
    });

    // 2. Khi bấm nút "Trước"
    $('#btn-prev-page').click(function(e) {
        e.preventDefault();
        if (currentPage > 1) loadHistory(currentPage - 1);
    });

    // 3. Khi bấm nút "Sau"
    $('#btn-next-page').click(function(e) {
        e.preventDefault();
        if (currentPage < totalPages) loadHistory(currentPage + 1);
    });

    // --- Chạy lần đầu ---
    loadHistory(1);
});