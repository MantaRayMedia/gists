$(document).ready(function () {

    /*
    * Selective filter summary initial call
    * Listener for removing selected
    *
    * @TODO: might add select and radios when we have first occurrence
    */
    getSelectiveFilterSummary();
    $(document).on('click', '.exposed-filter-summary .remove', function () {
        const data = $(this).data();
        switch (data.type) {
            case 'text':
                $('#' + data.id).val('')
                    .parents('.views-exposed-form')
                    .find('input.form-submit[id*=submit]')
                    .trigger('click');

                break;
            case 'checkbox':
                $('#' + data.id).trigger('click');
                break;
        }
    })
});


/*
 * Code for selective filter summary
 */
function getSelectiveFilterSummary() {
    const summaryContainer = $('.exposed-filter-summary');
    if (summaryContainer.length) {
        // REMOVE all invisible elements
        $('.element-invisible').remove();

        const container = summaryContainer.parent();

        let htmlData = [];
        let usedTitles = [];

        // first add text searches
        $.each(container.find('input[type=text]'), function() {
            const fieldWrapper = $(this).parents('[id$=-wrapper]');
            const title = $.trim(fieldWrapper.find('label').text());
            const value = fieldWrapper.find('input').val();

            if (value.length) {
                htmlData.push({
                    id: $(this).attr('id'),
                    type: 'text',
                    title: title,
                    value: value,
                    showTitle: true
                });
            }
        })

        // add all checkboxes/radios
        $.each(container.find('input:checked'), function() {
            const fieldWrapper = $(this).parent();
            const title = $.trim($(this).closest('.form-wrapper').find('.fieldset-title').text());
            const value = $.trim(fieldWrapper.find('label').text());

            let showTitle = true;
            if (usedTitles.indexOf(title) > -1) {
                showTitle = false;
            } else {
                usedTitles.push(title);
            }

            htmlData.push({
                id: $(this).attr('id'),
                type: $(this).attr('type'),
                title: title,
                value: value,
                showTitle: showTitle
            });
        })

        const listTemplate = ({ id, type, title, value, showTitle }) => `
        <li class="list-group-item">
          ${showTitle ? `<p class="list-group-item-text">${title}</p>` : ""}
          <span class="remove" data-id="${id}" data-type="${type}">x</span> ${value}
        </li>
      `;

        // clear all filters first
        summaryContainer.find('li').remove();
        summaryContainer.find('ul').html(htmlData.map(listTemplate).join(''));
    }
}

/*
 * this is a callback when ajax finishes with calls and page is updated
 */
jQuery(document).ajaxComplete(function(event, xhr, settings) {
    getSelectiveFilterSummary();
});