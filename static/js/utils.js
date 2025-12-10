function numberFormat(number = '0', decimalPlaces = 0) {
    let val = parseFloat(number);
    if (isNaN(val)) return "0";
    let fixed = val.toFixed(decimalPlaces);
    let parts = fixed.split('.');
    let integerPart = parts[0];
    let decimalPart = parts.length > 1 ? parts[1] : '';
    integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');

    if (decimalPlaces > 0) {
        decimalPart = decimalPart.replace(/0+$/, '');
        if (decimalPart.length > 0) {
            return integerPart + '.' + decimalPart;
        }
    }
    return integerPart;
}

// Hàm xử lý ký tự đặc biệt để chống lỗi XSS
function escapeHTML(str) {
    if (str === null || str === undefined) {
        return '';
    }
    return String(str).replace(/[&<>"']/g, function (tag) {
        const chars = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;'
        };
        return chars[tag] || tag;
    });
}

// Hàm hiệu ứng Loading cho nút bấm
function setLoading(buttonSelector, isLoading, loadingText = 'Đang xử lý...') {
    const btn = $(buttonSelector);
    if (isLoading) {
        btn.data('original-text', btn.html()); // Lưu text cũ
        btn.prop('disabled', true);
        btn.html(`<i class="fa fa-spinner fa-spin"></i> ${loadingText}`);
    } else {
        btn.prop('disabled', false);
        const original = btn.data('original-text');
        if (original) btn.html(original);
    }
}

// Cấu hình Ajax toàn cục (Token CSRF, Loading, Xử lý lỗi 401)
$(document).ready(function () {
    var csrf_token = $('meta[name=csrf-token]').attr('content');

    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrf_token);
            }
            // Tự động hiện loading nếu không tắt
            if (settings.global !== false) {
                if ($('#ajax-loader').length === 0) {
                    $('body').append('<div id="ajax-loader" style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;"><i class="fa fa-spinner fa-spin fa-3x" style="color:white;"></i></div>');
                }
            }
        },
        complete: function (xhr, status) {
            // Ẩn Loading
            $('#ajax-loader').remove();
        },
        error: function (xhr) {
            if (xhr.status === 401) {
                alert("⏳ Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại!");
                window.location.href = "login.html";
            }
        }
    });
});