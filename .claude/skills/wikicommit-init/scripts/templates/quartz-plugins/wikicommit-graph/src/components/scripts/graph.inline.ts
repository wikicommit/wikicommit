// @ts-nocheck
// Fork of github:quartz-community/graph's graph.inline.ts (Issue #584).
//
// The upstream file is left alone apart from four insertions, all marked
// "WikiCommit:" below:
//   1. filter config read out of dataset.cfg alongside the upstream keys
//   2. the filter applied to `neighbourhood` once it is settled and before
//      `nodes` is built — the single chokepoint downstream of which node
//      creation, link creation, the force simulation, collision radii and
//      drawing all fall into place on their own
//   3. the control bar, built here rather than in the component because the
//      option lists come from contentIndex
//   4. .global-graph-controls added to the click-outside exclusion list, so
//      operating the bar does not dismiss the modal
//
// The D3 force simulation and the PixiJS drawing code are untouched.
import { controlsSignature } from "../../util/controlBar";
import { collectFacets, filterNodes } from "../../util/nodeFilter";

import {
  removeAllChildren,
  getBasePath,
  getFullSlugFromUrl,
  simplifySlug,
  resolveBasePath,
} from "@quartz-community/utils";

(function () {
  function getSlugFromUrl() {
    var slug = getFullSlugFromUrl();
    var base = getBasePath();
    if (base && slug.startsWith(base.replace(/^\//, ""))) {
      slug = slug.slice(base.replace(/^\//, "").length);
      if (slug.startsWith("/")) slug = slug.slice(1);
    }
    return slug;
  }

  function loadScript(src) {
    var existing = document.querySelector('script[src="' + src + '"]');
    if (existing) return Promise.resolve();
    return new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      script.src = src;
      script.crossOrigin = "anonymous";
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  Promise.all([
    loadScript("https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"),
    loadScript("https://cdn.jsdelivr.net/npm/pixi.js@8/dist/pixi.js"),
  ])
    .then(function () {
      initGraph();
    })
    .catch(function (err) {
      console.error("[Graph] Failed to load libraries:", err);
      var containers = document.querySelectorAll(".graph-container");
      for (var i = 0; i < containers.length; i++) {
        containers[i].textContent = "Graph could not load. Check your network connection.";
        containers[i].style.display = "flex";
        containers[i].style.alignItems = "center";
        containers[i].style.justifyContent = "center";
        containers[i].style.color = "var(--gray)";
        containers[i].style.fontSize = "0.9rem";
      }
    });

  function initGraph() {
    var d3 = window.d3;
    var PIXI = window.PIXI;

    if (!d3 || !PIXI) {
      console.error("[Graph] Libraries not loaded");
      return;
    }

    var localStorageKey = "graph-visited";

    function getVisited() {
      return new Set(JSON.parse(localStorage.getItem(localStorageKey) || "[]"));
    }

    function addToVisited(slug) {
      var visited = getVisited();
      visited.add(slug);
      localStorage.setItem(localStorageKey, JSON.stringify(Array.from(visited)));
    }

    // Resolves CSS color values containing calc()/var() that PixiJS cannot parse.
    // Uses a temp DOM element so the browser's CSS engine evaluates the expression.
    function resolveColor(value, fallback) {
      if (!value) return fallback;
      var el = document.createElement("div");
      el.style.color = value;
      el.style.position = "absolute";
      el.style.visibility = "hidden";
      document.body.appendChild(el);
      var resolved = getComputedStyle(el).color;
      el.remove();
      return resolved || fallback;
    }

    // WikiCommit (3): control bar. Placed here rather than in the component
    // because the option lists (which languages and types exist) come from
    // contentIndex, which only this script has.
    var FILTER_STORAGE_KEY = "wikicommit-graph-filters";

    function loadStoredFilters() {
      // Rewriting dataset.cfg does not survive an SPA navigation, which
      // rebuilds the DOM from the server-rendered markup. localStorage is how
      // the upstream file already keeps `graph-visited` across navigations.
      try {
        var raw = localStorage.getItem(FILTER_STORAGE_KEY);
        if (!raw) return null;
        var parsed = JSON.parse(raw);
        return parsed && typeof parsed === "object" ? parsed : null;
      } catch {
        return null;
      }
    }

    function storeFilters(filters) {
      try {
        localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(filters));
      } catch {
        // Private browsing or a full quota: the filters simply do not persist.
      }
    }

    // WikiCommit (5): per-bar state kept across renders so renderControls() can
    // reuse the DOM it already built (Issue #651). Keyed on the bar element and
    // held weakly, so a bar replaced by an SPA navigation is simply not found
    // and its entry is collectable.
    var controlBarStates = new WeakMap();

    function readLabels(bar) {
      try {
        return JSON.parse(bar.dataset["labels"] || "{}");
      } catch {
        return {};
      }
    }

    function buildMultiSelect(labelText, values, selected, onChange) {
      var wrapper = document.createElement("label");
      wrapper.className = "global-graph-controls__field";
      var caption = document.createElement("span");
      caption.textContent = labelText;
      wrapper.appendChild(caption);

      var select = document.createElement("select");
      select.multiple = true;
      select.size = Math.min(Math.max(values.length, 2), 4);
      for (var i = 0; i < values.length; i++) {
        var option = document.createElement("option");
        option.value = values[i];
        option.textContent = values[i];
        // An empty selection means "all" (see filterNodes), so nothing is
        // marked selected in that case and the list reads as unconstrained.
        option.selected = selected.indexOf(values[i]) !== -1;
        select.appendChild(option);
      }
      select.addEventListener("change", function () {
        var picked = [];
        for (var i = 0; i < select.options.length; i++) {
          if (select.options[i].selected) picked.push(select.options[i].value);
        }
        onChange(picked);
      });
      wrapper.appendChild(select);
      // WikiCommit (5): `sync` writes a selection back into the options that
      // are already there, so a reused bar keeps focus and scroll position
      // (Issue #651). Only options whose selectedness actually differs are
      // written: assigning `selected` is a mutation as far as some engines are
      // concerned even when the value is unchanged, and it can move the
      // listbox's active option (the anchor a shift-range selection extends
      // from) or scroll it — on the very control this change exists to keep
      // usable from the keyboard. Same guard, same reason, as the degree
      // inputs below.
      return {
        field: wrapper,
        sync: function (selected2) {
          for (var j = 0; j < select.options.length; j++) {
            var wanted = selected2.indexOf(select.options[j].value) !== -1;
            if (select.options[j].selected !== wanted) select.options[j].selected = wanted;
          }
        },
      };
    }

    function buildToggle(labelText, checked, onChange) {
      var wrapper = document.createElement("label");
      wrapper.className = "global-graph-controls__field global-graph-controls__field--inline";
      var input = document.createElement("input");
      input.type = "checkbox";
      input.checked = checked;
      input.addEventListener("change", function () {
        onChange(input.checked);
      });
      wrapper.appendChild(input);
      var caption = document.createElement("span");
      caption.textContent = labelText;
      wrapper.appendChild(caption);
      return {
        field: wrapper,
        sync: function (checked2) {
          input.checked = checked2;
        },
      };
    }

    function buildDegreeRange(labelText, min, max, onChange) {
      var wrapper = document.createElement("label");
      wrapper.className = "global-graph-controls__field";
      var caption = document.createElement("span");
      caption.textContent = labelText;
      wrapper.appendChild(caption);

      var row = document.createElement("span");
      row.className = "global-graph-controls__range";
      var minInput = document.createElement("input");
      minInput.type = "number";
      minInput.min = "0";
      minInput.value = String(min || 0);
      var maxInput = document.createElement("input");
      maxInput.type = "number";
      maxInput.min = "0";
      maxInput.value = String(max || 0);
      // 0 at either end means "no bound"; a reader who wants to see isolated
      // pages leaves the low end at 0, and one hunting a hub raises the high
      // end off 0.
      minInput.title = "0 = no lower bound";
      maxInput.title = "0 = no upper bound";
      function emit() {
        onChange(
          Math.max(0, parseInt(minInput.value, 10) || 0),
          Math.max(0, parseInt(maxInput.value, 10) || 0),
        );
      }
      minInput.addEventListener("change", emit);
      maxInput.addEventListener("change", emit);
      row.appendChild(minInput);
      row.appendChild(maxInput);
      wrapper.appendChild(row);
      return {
        field: wrapper,
        // Only write when the text actually differs: assigning `value` resets
        // the caret in some engines even when the string is identical, and the
        // `change` event that got us here can fire on Enter with the field
        // still focused.
        sync: function (min2, max2) {
          var nextMin = String(min2 || 0);
          var nextMax = String(max2 || 0);
          if (minInput.value !== nextMin) minInput.value = nextMin;
          if (maxInput.value !== nextMax) maxInput.value = nextMax;
        },
      };
    }

    function renderControls(graphContainer, config, facets) {
      var outer = graphContainer.closest(".global-graph-outer");
      if (!outer) return;
      var bar = outer.querySelector(".global-graph-controls");
      if (!bar) return;

      var labels = readLabels(bar);
      var signature = controlsSignature(facets, labels);
      var state = controlBarStates.get(bar);

      // WikiCommit (5): reuse the bar when nothing about its structure changed
      // (Issue #651). Every control fires `update()`, which re-renders the
      // graph and lands back here, so rebuilding unconditionally meant losing
      // focus and scroll position on every click and keystroke. The values are
      // written back instead — skipping the rebuild without that write-back
      // would let Reset clear dataset.cfg while the controls still showed the
      // old selection. `graphContainer` is compared too because the listeners
      // built below close over it: an SPA navigation that replaces the modal
      // markup has to rebuild, and it does, since the bar element is new then
      // and this lookup misses.
      if (
        state &&
        state.signature === signature &&
        state.graphContainer === graphContainer &&
        bar.childElementCount > 0
      ) {
        for (var s = 0; s < state.syncers.length; s++) {
          state.syncers[s](config);
        }
        return;
      }

      removeAllChildren(bar);
      var syncers = [];

      function update(patch) {
        // Read the live cfg rather than the `config` this bar was built from:
        // once the bar outlives a render, that captured value is one or more
        // changes behind, and merging a patch into it would silently undo them.
        var current;
        try {
          current = JSON.parse(graphContainer.dataset["cfg"] || "{}");
        } catch {
          // Malformed cfg: fall back to what this bar was built from, the same
          // value renderGraph() would have been working with.
          current = config;
        }
        var next = Object.assign({}, current, patch);
        graphContainer.dataset["cfg"] = JSON.stringify(next);
        storeFilters({
          langs: next.langs || [],
          types: next.types || [],
          showSources: next.showSources !== false,
          showTags: next.showTags !== false,
          minDegree: next.minDegree || 0,
          maxDegree: next.maxDegree || 0,
        });
        showGlobalGraph();
      }

      if (facets.langs.length > 1) {
        var langControl = buildMultiSelect(
          labels.lang || "Language",
          facets.langs,
          config.langs || [],
          function (v) {
            update({ langs: v });
          },
        );
        bar.appendChild(langControl.field);
        syncers.push(function (cfg) {
          langControl.sync(cfg.langs || []);
        });
      }
      if (facets.types.length > 1) {
        var typeControl = buildMultiSelect(
          labels.type || "Type",
          facets.types,
          config.types || [],
          function (v) {
            update({ types: v });
          },
        );
        bar.appendChild(typeControl.field);
        syncers.push(function (cfg) {
          typeControl.sync(cfg.types || []);
        });
      }
      var sourcesControl = buildToggle(
        labels.sources || "Sources",
        config.showSources !== false,
        function (v) {
          update({ showSources: v });
        },
      );
      bar.appendChild(sourcesControl.field);
      syncers.push(function (cfg) {
        sourcesControl.sync(cfg.showSources !== false);
      });
      // Tags reuse the upstream showTags key, which is read where links are
      // built — so this toggle needs no filtering code of its own.
      var tagsControl = buildToggle(labels.tags || "Tags", config.showTags !== false, function (v) {
        update({ showTags: v });
      });
      bar.appendChild(tagsControl.field);
      syncers.push(function (cfg) {
        tagsControl.sync(cfg.showTags !== false);
      });
      var degreeControl = buildDegreeRange(
        labels.degree || "Links per node",
        config.minDegree || 0,
        config.maxDegree || 0,
        function (min, max) {
          update({ minDegree: min, maxDegree: max });
        },
      );
      bar.appendChild(degreeControl.field);
      syncers.push(function (cfg) {
        degreeControl.sync(cfg.minDegree || 0, cfg.maxDegree || 0);
      });

      var reset = document.createElement("button");
      reset.type = "button";
      reset.className = "global-graph-controls__reset";
      reset.textContent = labels.reset || "Reset";
      reset.addEventListener("click", function () {
        update({
          langs: [],
          types: [],
          showSources: true,
          showTags: true,
          minDegree: 0,
          maxDegree: 0,
        });
      });
      bar.appendChild(reset);

      controlBarStates.set(bar, {
        signature: signature,
        graphContainer: graphContainer,
        syncers: syncers,
      });
    }

    async function renderGraph(graph, fullSlug, renderGeneration) {
      var slug = simplifySlug(fullSlug);
      if (slug === "") slug = "index";
      var visited = getVisited();
      removeAllChildren(graph);

      if (renderGeneration !== undefined && renderGeneration !== currentRenderGeneration) {
        console.log("[Graph] Stale render, skipping");
        return function () {};
      }

      var config = JSON.parse(graph.dataset["cfg"] || "{}");
      var enableDrag = config.drag;
      var enableZoom = config.zoom;
      var depth = config.depth;
      var scale = config.scale || 1;
      var repelForce = config.repelForce || 0.5;
      var centerForce = config.centerForce || 0.3;
      var linkDistance = config.linkDistance || 30;
      var fontSize = config.fontSize || 0.6;
      var opacityScale = config.opacityScale || 1;
      var removeTags = config.removeTags || [];
      var showTags = config.showTags;
      var focusOnHover = config.focusOnHover;
      var enableRadial = config.enableRadial;
      // WikiCommit (1): the fork's own keys. The control bar writes these back
      // into dataset.cfg and re-renders; because renderGraph() re-parses
      // dataset.cfg on every call (rather than reading it once at startup),
      // that is all it takes for a change to take effect.
      var showControls = config.showControls;
      var filterConfig = {
        langs: config.langs || [],
        types: config.types || [],
        showSources: config.showSources !== false,
        minDegree: config.minDegree || 0,
        maxDegree: config.maxDegree || 0,
      };

      var data;
      try {
        var dataRaw = await fetchData;
        data = new Map();
        for (var key in dataRaw) {
          data.set(simplifySlug(key), dataRaw[key]);
        }
      } catch (err) {
        console.error("[Graph] Error loading data:", err);
        return function () {};
      }

      var width = graph.offsetWidth;
      var height = Math.max(graph.offsetHeight, 250);

      var links = [];
      var allTags = [];
      var validLinks = new Set(data.keys());

      data.forEach(function (details, source) {
        var outgoing = details.links || [];
        for (var i = 0; i < outgoing.length; i++) {
          var dest = simplifySlug(outgoing[i]);
          if (validLinks.has(dest)) {
            links.push({ source: source, target: dest });
          }
        }

        if (showTags) {
          var tags = details.tags || [];
          for (var i = 0; i < tags.length; i++) {
            var tag = tags[i];
            if (removeTags.indexOf(tag) === -1) {
              var tagSlug = simplifySlug("tags/" + tag);
              if (allTags.indexOf(tagSlug) === -1) {
                allTags.push(tagSlug);
              }
              links.push({ source: source, target: tagSlug });
            }
          }
        }
      });

      var neighbourhood = new Set();
      if (depth >= 0) {
        var queue = [slug];
        var seen = new Set([slug]);
        for (var d = 0; d <= depth && queue.length > 0; d++) {
          var nextQueue = [];
          for (var qi = 0; qi < queue.length; qi++) {
            var cur = queue[qi];
            neighbourhood.add(cur);
            for (var li = 0; li < links.length; li++) {
              var link = links[li];
              if (link.source === cur && !seen.has(link.target)) {
                seen.add(link.target);
                nextQueue.push(link.target);
              }
              if (link.target === cur && !seen.has(link.source)) {
                seen.add(link.source);
                nextQueue.push(link.source);
              }
            }
          }
          queue = nextQueue;
        }
      } else {
        validLinks.forEach(function (id) {
          neighbourhood.add(id);
        });
        for (var i = 0; i < allTags.length; i++) {
          neighbourhood.add(allTags[i]);
        }
      }

      // WikiCommit (2): narrow `neighbourhood` before anything is built from
      // it. Only for the global graph (depth < 0): the depth >= 0 branch above
      // grows `neighbourhood` by BFS from the current page, so removing a node
      // from it afterwards can cut the path that put its neighbours there and
      // leave them stranded. The global graph starts from every node at once
      // and has no such paths to break.
      if (depth < 0) {
        neighbourhood = filterNodes(neighbourhood, links, filterConfig);
      }

      // WikiCommit (3): the bar is rebuilt from the *unfiltered* node set, so
      // narrowing to one language does not remove the other languages from the
      // dropdown that would let you get back.
      if (showControls && depth < 0) {
        var unfiltered = new Set();
        validLinks.forEach(function (id) {
          unfiltered.add(id);
        });
        renderControls(graph, config, collectFacets(unfiltered));
      }

      var nodes = [];
      var nodeMap = new Map();
      neighbourhood.forEach(function (url) {
        var isTag = url.startsWith("tags/");
        var text = isTag ? "#" + url.substring(5) : data.get(url)?.title || url;
        var nodeTags = isTag ? [] : data.get(url)?.tags || [];
        var node = {
          id: url,
          text: text,
          tags: nodeTags,
          x: Math.random() * width - width / 2,
          y: Math.random() * height - height / 2,
          vx: 0,
          vy: 0,
        };
        nodes.push(node);
        nodeMap.set(url, node);
      });

      var graphLinks = [];
      for (var i = 0; i < links.length; i++) {
        var link = links[i];
        if (neighbourhood.has(link.source) && neighbourhood.has(link.target)) {
          var sourceNode = nodeMap.get(link.source);
          var targetNode = nodeMap.get(link.target);
          if (sourceNode && targetNode) {
            graphLinks.push({ source: sourceNode, target: targetNode });
          }
        }
      }

      var styles = getComputedStyle(document.documentElement);
      var secondary = resolveColor(styles.getPropertyValue("--secondary").trim(), "#c792ea");
      var tertiary = resolveColor(styles.getPropertyValue("--tertiary").trim(), "#82aaff");
      var gray = resolveColor(styles.getPropertyValue("--gray").trim(), "#6c6c6c");
      var lightgray = resolveColor(styles.getPropertyValue("--lightgray").trim(), "#d4d4d4");
      var dark = resolveColor(styles.getPropertyValue("--dark").trim(), "#1a1a1a");
      var light = resolveColor(styles.getPropertyValue("--light").trim(), "#f5f5f5");
      var bodyFont = styles.getPropertyValue("--bodyFont").trim() || "inherit";

      var app = new PIXI.Application();
      await app.init({
        width: width,
        height: height,
        antialias: true,
        backgroundAlpha: 0,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
        eventMode: "static",
      });

      graph.appendChild(app.canvas);

      var stage = new PIXI.Container();
      app.stage.addChild(stage);

      var simulation = d3
        .forceSimulation(nodes)
        .force("charge", d3.forceManyBody().strength(-100 * repelForce))
        .force("center", d3.forceCenter().strength(centerForce))
        .force("link", d3.forceLink(graphLinks).distance(linkDistance))
        .force(
          "collide",
          d3
            .forceCollide()
            .radius(function (d) {
              var numLinks = 0;
              for (var i = 0; i < graphLinks.length; i++) {
                if (graphLinks[i].source.id === d.id || graphLinks[i].target.id === d.id) {
                  numLinks++;
                }
              }
              return 2 + Math.sqrt(numLinks);
            })
            .iterations(3),
        );

      if (enableRadial) {
        var radius = (Math.min(width, height) / 2) * 0.8;
        simulation.force("radial", d3.forceRadial(radius).strength(0.2));
      }

      var linkContainer = new PIXI.Container();
      var nodesContainer = new PIXI.Container();
      var labelsContainer = new PIXI.Container();
      stage.addChild(linkContainer);
      stage.addChild(nodesContainer);
      stage.addChild(labelsContainer);

      var nodeRenderData = [];
      var linkRenderData = [];
      var hoveredNodeId = null;
      var hoveredNeighbours = new Set();
      var dragStartTime = 0;
      var dragging = false;
      var currentTransform = d3.zoomIdentity;

      function nodeRadius(d) {
        var numLinks = 0;
        for (var i = 0; i < graphLinks.length; i++) {
          if (graphLinks[i].source.id === d.id || graphLinks[i].target.id === d.id) {
            numLinks++;
          }
        }
        return 2 + Math.sqrt(numLinks);
      }

      function nodeColor(d) {
        var isCurrent = d.id === slug;
        if (isCurrent) {
          return secondary;
        } else if (visited.has(d.id) || d.id.startsWith("tags/")) {
          return tertiary;
        } else {
          return gray;
        }
      }

      function updateHoverInfo(newHoveredId) {
        hoveredNodeId = newHoveredId;

        if (newHoveredId === null) {
          hoveredNeighbours = new Set();
          for (var i = 0; i < nodeRenderData.length; i++) {
            nodeRenderData[i].active = false;
          }
          for (var i = 0; i < linkRenderData.length; i++) {
            linkRenderData[i].active = false;
          }
        } else {
          hoveredNeighbours = new Set();

          for (var i = 0; i < linkRenderData.length; i++) {
            var linkData = linkRenderData[i].simulationData;
            if (linkData.source.id === newHoveredId || linkData.target.id === newHoveredId) {
              hoveredNeighbours.add(linkData.source.id);
              hoveredNeighbours.add(linkData.target.id);
              linkRenderData[i].active = true;
            } else {
              linkRenderData[i].active = false;
            }
          }

          hoveredNeighbours.add(newHoveredId);

          for (var i = 0; i < nodeRenderData.length; i++) {
            if (hoveredNeighbours.has(nodeRenderData[i].simulationData.id)) {
              nodeRenderData[i].active = true;
            } else {
              nodeRenderData[i].active = false;
            }
          }
        }
      }

      function renderLinks() {
        for (var i = 0; i < linkRenderData.length; i++) {
          var linkData = linkRenderData[i];
          var alpha = 1;
          if (hoveredNodeId !== null) {
            alpha = linkData.active ? 1 : 0.2;
          }
          linkData.alpha = alpha;
          linkData.color = linkData.active ? gray : lightgray;
        }
      }

      function renderLabels() {
        var defaultScale = 1 / scale;
        var activeScale = defaultScale * 1.1;

        for (var i = 0; i < nodeRenderData.length; i++) {
          var nodeData = nodeRenderData[i];
          if (hoveredNodeId === nodeData.simulationData.id) {
            nodeData.label.alpha = 1;
            nodeData.label.scale.set(activeScale);
          } else {
            nodeData.label.scale.set(defaultScale);
          }
        }
      }

      function renderNodes() {
        for (var i = 0; i < nodeRenderData.length; i++) {
          var nodeData = nodeRenderData[i];
          var alpha = 1;
          if (hoveredNodeId !== null && focusOnHover) {
            alpha = nodeData.active ? 1 : 0.2;
          }
          nodeData.gfx.alpha = alpha;
        }
      }

      function renderPixiFromD3() {
        renderNodes();
        renderLinks();
        renderLabels();
      }

      for (var i = 0; i < nodes.length; i++) {
        var node = nodes[i];
        var nodeId = node.id;
        var isTagNode = nodeId.startsWith("tags/");
        var radius = nodeRadius(node);
        var color = nodeColor(node);

        var label = new PIXI.Text({
          text: node.text,
          style: {
            fontSize: fontSize * 15,
            fill: dark,
            fontFamily: bodyFont,
          },
          resolution: window.devicePixelRatio * 4,
        });
        label.anchor.set(0.5, 1.2);
        label.alpha = 0;
        label.scale.set(1 / scale);
        labelsContainer.addChild(label);

        var gfx = new PIXI.Graphics();
        gfx.circle(0, 0, radius);
        gfx.fill({ color: isTagNode ? light : color });
        if (isTagNode) {
          gfx.stroke({ width: 2, color: tertiary });
        }

        gfx.eventMode = "static";
        gfx.cursor = "pointer";
        gfx.label = nodeId;

        (function (n, g, labelRef) {
          var oldLabelOpacity = 0;
          g.on("pointerover", function (e) {
            updateHoverInfo(n.id);
            oldLabelOpacity = labelRef.alpha;
            if (!dragging) {
              renderPixiFromD3();
            }
          });

          g.on("pointerleave", function () {
            updateHoverInfo(null);
            labelRef.alpha = oldLabelOpacity;
            if (!dragging) {
              renderPixiFromD3();
            }
          });
        })(node, gfx, label);

        nodesContainer.addChild(gfx);

        nodeRenderData.push({
          simulationData: node,
          gfx: gfx,
          label: label,
          color: color,
          alpha: 1,
          active: false,
        });
      }

      for (var i = 0; i < graphLinks.length; i++) {
        var link = graphLinks[i];
        var gfx = new PIXI.Graphics();
        gfx.eventMode = "none";
        linkContainer.addChild(gfx);

        linkRenderData.push({
          simulationData: link,
          gfx: gfx,
          color: lightgray,
          alpha: 1,
          active: false,
        });
      }

      if (enableDrag) {
        var dragSubject = function (event) {
          var mouseX = (event.x - currentTransform.x) / currentTransform.k;
          var mouseY = (event.y - currentTransform.y) / currentTransform.k;

          for (var i = 0; i < nodes.length; i++) {
            var n = nodes[i];
            var dx = mouseX - n.x - width / 2;
            var dy = mouseY - n.y - height / 2;
            var dist = Math.sqrt(dx * dx + dy * dy);
            var rad = nodeRadius(n);
            if (dist < rad + 5) {
              return n;
            }
          }
          return null;
        };

        var dragStarted = function (event) {
          if (!event.active) simulation.alphaTarget(1).restart();
          event.subject.fx = event.subject.x;
          event.subject.fy = event.subject.y;
          var mouseSimX = (event.x - currentTransform.x) / currentTransform.k - width / 2;
          var mouseSimY = (event.y - currentTransform.y) / currentTransform.k - height / 2;
          event.subject.__dragOffset = {
            x: mouseSimX - event.subject.x,
            y: mouseSimY - event.subject.y,
          };
          dragStartTime = Date.now();
          dragging = true;
          hoveredNodeId = event.subject.id;
        };

        var dragDragged = function (event) {
          var mouseSimX = (event.x - currentTransform.x) / currentTransform.k - width / 2;
          var mouseSimY = (event.y - currentTransform.y) / currentTransform.k - height / 2;
          event.subject.fx = mouseSimX - event.subject.__dragOffset.x;
          event.subject.fy = mouseSimY - event.subject.__dragOffset.y;
        };

        var dragEnded = function (event) {
          if (!event.active) simulation.alphaTarget(0);
          event.subject.fx = null;
          event.subject.fy = null;
          dragging = false;
          updateHoverInfo(null);
          renderPixiFromD3();

          if (Date.now() - dragStartTime < 500) {
            var target = resolveBasePath(event.subject.id);
            window.location.href = target;
          }
        };

        var drag = d3
          .drag()
          .container(app.canvas)
          .subject(dragSubject)
          .on("start", dragStarted)
          .on("drag", dragDragged)
          .on("end", dragEnded);

        d3.select(app.canvas).call(drag);
      } else {
        for (var i = 0; i < nodeRenderData.length; i++) {
          (function (nodeData) {
            nodeData.gfx.on("click", function () {
              var target = resolveBasePath(nodeData.simulationData.id);
              window.location.href = target;
            });
          })(nodeRenderData[i]);
        }
      }

      if (enableZoom) {
        var zoomed = function (event) {
          currentTransform = event.transform;
          stage.scale.set(currentTransform.k, currentTransform.k);
          stage.position.set(currentTransform.x, currentTransform.y);

          var newScale = currentTransform.k * opacityScale;
          var scaleOpacity = Math.max((newScale - 1) / 3.75, 0);

          var activeLabels = [];
          for (var i = 0; i < nodeRenderData.length; i++) {
            if (nodeRenderData[i].active) {
              activeLabels.push(nodeRenderData[i].label);
            }
          }

          for (var i = 0; i < labelsContainer.children.length; i++) {
            var label = labelsContainer.children[i];
            if (activeLabels.indexOf(label) === -1) {
              label.alpha = scaleOpacity;
            }
          }
        };

        var zoom = d3
          .zoom()
          .extent([
            [0, 0],
            [width, height],
          ])
          .scaleExtent([0.25, 4])
          .on("zoom", zoomed);

        d3.select(app.canvas).call(zoom);
      }

      var stopAnimation = false;
      function animate() {
        if (stopAnimation) return;

        for (var i = 0; i < nodeRenderData.length; i++) {
          var n = nodeRenderData[i];
          var x = n.simulationData.x;
          var y = n.simulationData.y;
          if (x != null && y != null) {
            n.gfx.position.set(x + width / 2, y + height / 2);
            if (n.label) {
              n.label.position.set(x + width / 2, y + height / 2);
            }
          }
        }

        for (var i = 0; i < linkRenderData.length; i++) {
          var l = linkRenderData[i];
          var linkData = l.simulationData;
          var sx = linkData.source.x;
          var sy = linkData.source.y;
          var tx = linkData.target.x;
          var ty = linkData.target.y;
          if (sx != null && sy != null && tx != null && ty != null) {
            l.gfx.clear();
            l.gfx.moveTo(sx + width / 2, sy + height / 2);
            l.gfx.lineTo(tx + width / 2, ty + height / 2);
            l.gfx.stroke({ alpha: l.alpha, width: 1, color: l.color });
          }
        }

        requestAnimationFrame(animate);
      }

      simulation.on("tick", function () {});
      simulation.restart();
      renderPixiFromD3();
      animate();

      return function () {
        stopAnimation = true;
        simulation.stop();
        try {
          app.destroy(true);
        } catch (_) {
          // PixiJS may throw if WebGL context was already lost.
        }
      };
    }

    var localCleanups = [];
    var globalCleanups = [];
    var currentRenderGeneration = 0;
    var globalRenderToken = 0;

    function cleanupLocal() {
      for (var i = 0; i < localCleanups.length; i++) {
        localCleanups[i]();
      }
      localCleanups = [];
    }

    function cleanupGlobal() {
      // WikiCommit (3): invalidate any global render still in flight. The
      // control bar re-renders the graph on every `change` event, so two
      // changes a few milliseconds apart (ctrl-clicking two options, a toggle
      // followed by Reset) start two renderGraph() runs on the same
      // container. renderGraph() only appends its canvas and hands back its
      // cleanup after `await app.init()`, and showGlobalGraph() passes no
      // render generation, so without this token the earlier run would append
      // a second canvas and register its cleanup after this reset — leaving a
      // detached PixiJS app animating until the next open/close.
      globalRenderToken++;
      for (var i = 0; i < globalCleanups.length; i++) {
        globalCleanups[i]();
      }
      globalCleanups = [];
    }

    var globalContainers = [];
    var globalIcons = [];
    var documentClickHandler = null;
    var documentKeydownHandler = null;
    var iconClickHandler = null;

    function hideGlobalGraph() {
      cleanupGlobal();
      for (var i = 0; i < globalContainers.length; i++) {
        globalContainers[i].classList.remove("active");
        var sidebar = globalContainers[i].closest(".sidebar");
        if (sidebar) {
          sidebar.style.zIndex = "";
        }
      }
    }

    function anyGlobalGraphActive() {
      for (var i = 0; i < globalContainers.length; i++) {
        if (globalContainers[i].classList.contains("active")) {
          return true;
        }
      }
      return false;
    }

    function showGlobalGraph() {
      cleanupGlobal();
      var renderToken = globalRenderToken;
      var currentSlug = getSlugFromUrl();
      for (var i = 0; i < globalContainers.length; i++) {
        var container = globalContainers[i];
        container.classList.add("active");
        var sidebar = container.closest(".sidebar");
        if (sidebar) {
          sidebar.style.zIndex = "1";
        }

        var graphContainer = container.querySelector(".global-graph-container");
        if (graphContainer) {
          // WikiCommit (3): reapply the persisted filters before rendering, so
          // an SPA navigation (which restores the server-rendered dataset.cfg)
          // does not silently reset them.
          var stored = loadStoredFilters();
          if (stored) {
            try {
              var base = JSON.parse(graphContainer.dataset["cfg"] || "{}");
              graphContainer.dataset["cfg"] = JSON.stringify(Object.assign(base, stored));
            } catch {
              // Malformed cfg: leave it for renderGraph() to fall back on.
            }
          }
          (function (gc) {
            renderGraph(gc, currentSlug, undefined)
              .then(function (cleanup) {
                if (renderToken !== globalRenderToken) {
                  // Superseded (or the modal was closed) while this render was
                  // still awaiting app.init(): tear it down now rather than
                  // registering it for a cleanup that has already run.
                  cleanup();
                  return;
                }
                globalCleanups.push(cleanup);
              })
              .catch(function (err) {
                console.error("[Graph] Global render error:", err);
              });
          })(graphContainer);
        }
      }
    }

    function toggleGlobalGraph() {
      if (anyGlobalGraphActive()) {
        hideGlobalGraph();
      } else {
        showGlobalGraph();
      }
    }

    function renderLocal() {
      cleanupLocal();
      var thisGeneration = ++currentRenderGeneration;
      var slug = getSlugFromUrl();
      addToVisited(slug);

      var localContainers = document.querySelectorAll(".graph-container");
      for (var i = 0; i < localContainers.length; i++) {
        (function (container) {
          renderGraph(container, slug, thisGeneration)
            .then(function (cleanup) {
              if (thisGeneration === currentRenderGeneration) {
                localCleanups.push(cleanup);
              }
            })
            .catch(function (err) {
              console.error("[Graph] Local render error:", err);
            });
        })(localContainers[i]);
      }
    }

    function handleNav(e) {
      var slug = e.detail ? e.detail.url : getSlugFromUrl();
      addToVisited(simplifySlug(slug));

      renderLocal();

      globalContainers = Array.from(document.querySelectorAll(".global-graph-outer"));

      if (iconClickHandler) {
        for (var i = 0; i < globalIcons.length; i++) {
          globalIcons[i].removeEventListener("click", iconClickHandler);
        }
      }

      globalIcons = Array.from(document.querySelectorAll(".global-graph-icon"));
      iconClickHandler = function () {
        toggleGlobalGraph();
      };
      for (var i = 0; i < globalIcons.length; i++) {
        globalIcons[i].addEventListener("click", iconClickHandler);
      }

      if (documentClickHandler) {
        document.removeEventListener("click", documentClickHandler);
      }
      documentClickHandler = function (e) {
        if (anyGlobalGraphActive()) {
          var inContainer = e.target.closest(".global-graph-container");
          var inIcon = e.target.closest(".global-graph-icon");
          // WikiCommit (4): the control bar is a sibling of
          // .global-graph-container (it has to be — renderGraph() empties that
          // container on every render), so without this every click on the bar
          // counts as a click outside and dismisses the modal.
          var inControls = e.target.closest(".global-graph-controls");
          if (!inContainer && !inIcon && !inControls) {
            hideGlobalGraph();
          }
        }
      };
      document.addEventListener("click", documentClickHandler);

      if (documentKeydownHandler) {
        document.removeEventListener("keydown", documentKeydownHandler);
      }
      documentKeydownHandler = function (e) {
        if (e.key === "Escape") {
          if (anyGlobalGraphActive()) {
            hideGlobalGraph();
          }
          return;
        }

        if (e.key === "g" && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
          e.preventDefault();
          toggleGlobalGraph();
        }
      };
      document.addEventListener("keydown", documentKeydownHandler);

      if (anyGlobalGraphActive()) {
        showGlobalGraph();
      }
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () {
        handleNav({ detail: { url: getSlugFromUrl() } });
      });
    } else {
      handleNav({ detail: { url: getSlugFromUrl() } });
    }
    document.addEventListener("prenav", function () {
      cleanupLocal();
      cleanupGlobal();
    });
    document.addEventListener("nav", handleNav);
    document.addEventListener("render", handleNav);

    function handleThemeChange() {
      renderLocal();
      if (anyGlobalGraphActive()) {
        showGlobalGraph();
      }
    }
    document.addEventListener("themechange", handleThemeChange);
  }
})();
