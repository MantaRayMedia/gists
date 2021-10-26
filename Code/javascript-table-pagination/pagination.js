(function ($) {
  let perPage = 20;

  function genTables() {
    let tables = $("table.pagination");
    console.log(tables.length)
    for (let i = 0; i < tables.length; i++) {
      perPage = parseInt(tables[i].dataset.pagecount || perPage);
      createFooters(tables[i]);
      createTableMeta(tables[i]);
      loadTable(tables[i]);
    }
  }

  // based on current page, only show the elements in that range
  function loadTable(table) {
    let startIndex = 0;

    if (table.querySelector("th")) {
      startIndex = 1;
    }

    let start = (parseInt(table.dataset.currentpage) * table.dataset.pagecount) + startIndex;
    let end = start + parseInt(table.dataset.pagecount);
    let rows = table.rows;

    for (let x = startIndex; x < rows.length; x++) {
      if (x < start || x >= end) {
        rows[x].classList.add("inactive");
      } else {
        rows[x].classList.remove("inactive");
      }
    }
  }

  function createTableMeta(table) {
    table.dataset.currentpage = "0";
  }
  function createFooters(table) {
    let hasHeader = false;
    if (table.querySelector("th")) {
      hasHeader = true;
    }
    let rows = table.rows.length;

    if (hasHeader) {
      rows = rows - 1;
    }

    let numPages = rows / perPage;
    let pager = document.createElement("div");

    // add an extra page, if we're
    if (numPages % 1 > 0) {
      numPages = Math.floor(numPages) + 1;
    }

    pager.className = "pager";
    for (let i = 0; i < numPages ; i++) {
      let page = document.createElement("div");
      page.innerHTML = i + 1;
      page.className = "pager-item";
      page.dataset.index = i;

      if (i === 0) {
        page.classList.add("selected");
      }

      page.addEventListener('click', function() {
        let parent = this.parentNode;
        let items = parent.querySelectorAll(".pager-item");
        for (let x = 0; x < items.length; x++) {
          items[x].classList.remove("selected");
        }
        this.classList.add('selected');
        table.dataset.currentpage = this.dataset.index;
        loadTable(table);
      });
      pager.appendChild(page);
    }

    // insert page at the top of the table
    table.parentNode.insertBefore(pager, table);
  }

  // call the generation
  document.addEventListener("DOMContentLoaded", function(){
    genTables();
  });
})(jQuery);
