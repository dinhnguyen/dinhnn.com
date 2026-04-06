const Gallery = (selector) => {
  const parseItems = (grid) => {
    return Array.from(grid.children).map((div) => {
      const link = div.children[0];
      const size = link.getAttribute("data-size").split("x");
      const img = link.children[0];

      return {
        div,
        src: link.getAttribute("href"),
        w: parseInt(size[0], 10),
        h: parseInt(size[1], 10),
        msrc: img.getAttribute("src"),
        title: link.getAttribute("data-caption") || "",
      };
    });
  };

  const openGallery = (grid, index) => {
    const pswp = document.querySelectorAll(".pswp")[0];
    const items = parseItems(grid);

    const getThumbBoundsFn = (i) => {
      const offset = window.pageYOffset || document.documentElement.scrollTop;
      const img = items[i].div.getElementsByTagName("img")[0];
      const rect = img.getBoundingClientRect();

      return { x: rect.left, y: rect.top + offset, w: rect.width };
    };

    const keepAspectRatio = grid.classList.contains("keep-aspect-ratio");
    const options = {
      index,
      getThumbBoundsFn: keepAspectRatio ? getThumbBoundsFn : undefined,
    };

    const gallery = new PhotoSwipe(pswp, PhotoSwipeUI_Default, items, options);
    gallery.init();
  };

  const openGalleryFromHash = (grid) => {
    const hash = new URLSearchParams(window.location.hash.substr(1));

    const pid = hash.get("pid"),
      gid = hash.get("gid");

    if (!pid || !gid) return;

    openGallery(grid, parseInt(pid, 10));
  };

  const grid = document.querySelectorAll(selector)[0];
  Array.from(grid.children).forEach((div, index) => {
    const img = div.getElementsByTagName("img")[0];
    if (!img) return;
    img.onclick = (e) => {
      (e || window.event).preventDefault();
      openGallery(grid, index);
      return false;
    };
  });

  openGalleryFromHash(grid);
};

Gallery(".grid");
