/**
 * Function to get size of any element, even hidden
 * @returns {{width: *, height}}
 */
jQuery.fn.getSize = function () {
  const $wrap = jQuery("<div />").appendTo(jQuery("body"));
  $wrap.css({
    "position": "absolute !important",
    "visibility": "hidden !important",
    "display": "block !important"
  });

  const $clone = jQuery(this).clone().appendTo($wrap);

  const size = {
    "width": $clone.width(),
    "height": $clone.height()
  };

  $wrap.remove();

  return size;
}

const hiddenElmSize = $('#element').getSize();
const elementHeight = (hiddenElmSize.height > carouselHeight) ? hiddenElmSize.height : carouselHeight;