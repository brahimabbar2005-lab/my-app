/**
 * ComeMorocco AI — embeddable chat widget.
 *
 * Design notes:
 *
 * Shadow DOM. The widget drops into whatever WordPress theme the site runs,
 * and themes set aggressive global styles (`* { box-sizing }`, `button {}`,
 * `p { margin }`). A shadow root is the only reliable way to keep the widget
 * looking the same on every page without an !important arms race.
 *
 * No web fonts. The widget inherits nothing and loads nothing — a chat panel
 * is not worth 60kB of font on a phone on Moroccan mobile data, and a system
 * stack sits more naturally inside a host site than a second typeface would.
 *
 * Palette is ComeMorocco's own: the deep green and amber already used in the
 * site's booking widget configs, not a generic assistant blue.
 *
 * No dependencies, no build step. One file the plugin can enqueue.
 */
(function () {
  "use strict";

  var DEFAULTS = {
    apiBase: "http://localhost:8000",
    widgetKey: null,
    locale: (document.documentElement.lang || "en").slice(0, 2),
    position: "right",
    greeting: null,
    openOnLoad: false
  };

  var STRINGS = {
    en: {
      title: "Ask about Morocco",
      subtitle: "Travel questions, answered properly",
      placeholder: "Ask anything about travelling in Morocco…",
      send: "Send",
      open: "Ask about Morocco",
      close: "Close chat",
      restart: "New conversation",
      thinking: "Thinking…",
      helpful: "Helpful",
      notHelpful: "Not helpful",
      thanks: "Thanks — that helps.",
      whatWrong: "What was wrong?",
      disclosure: "Partner link",
      aiNotice: "AI answers. Check anything time-sensitive before you book.",
      readMore: "Read more",
      error: "Something went wrong. Try again in a moment.",
      reasons: {
        incorrect: "Incorrect",
        outdated: "Out of date",
        irrelevant: "Not relevant",
        too_long: "Too long",
        did_not_answer: "Didn't answer it",
        other: "Something else"
      }
    },
    fr: {
      title: "Une question sur le Maroc ?",
      subtitle: "Des réponses concrètes pour votre voyage",
      placeholder: "Posez votre question sur le Maroc…",
      send: "Envoyer",
      open: "Une question sur le Maroc ?",
      close: "Fermer",
      restart: "Nouvelle conversation",
      thinking: "Un instant…",
      helpful: "Utile",
      notHelpful: "Pas utile",
      thanks: "Merci, c'est noté.",
      whatWrong: "Qu'est-ce qui n'allait pas ?",
      disclosure: "Lien partenaire",
      aiNotice: "Réponses générées par IA. Vérifiez les informations qui changent avant de réserver.",
      readMore: "Lire l'article",
      error: "Une erreur s'est produite. Réessayez dans un instant.",
      reasons: {
        incorrect: "Inexact",
        outdated: "Plus à jour",
        irrelevant: "Hors sujet",
        too_long: "Trop long",
        did_not_answer: "Ne répond pas",
        other: "Autre"
      }
    }
  };

  var CSS = [
    ":host{all:initial}",
    "*,*::before,*::after{box-sizing:border-box}",
    ":host{",
    "--ink:#15201b;--ink-soft:#5a6b62;--line:#dfe5e0;--bg:#ffffff;--bg-soft:#f4f7f4;",
    "--green:#0c3b2e;--green-bright:#006233;--amber:#ffba00;--danger:#a3341f;",
    "--radius:14px;--shadow:0 12px 34px rgba(12,59,46,.18);",
    "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;",
    "font-size:15px;line-height:1.55;color:var(--ink);}",

    /* launcher */
    ".launcher{position:fixed;bottom:20px;z-index:2147483000;display:inline-flex;align-items:center;",
    "gap:9px;padding:13px 19px;border:0;border-radius:999px;background:var(--green);color:#fff;",
    "font:inherit;font-weight:600;font-size:14.5px;cursor:pointer;box-shadow:var(--shadow);}",
    ".launcher:hover{background:var(--green-bright)}",
    ".launcher:focus-visible{outline:3px solid var(--amber);outline-offset:3px}",
    ".launcher.right{right:20px}.launcher.left{left:20px}",
    ".launcher .flag{font-size:17px;line-height:1}",

    /* panel */
    ".panel{position:fixed;bottom:20px;z-index:2147483000;width:392px;max-width:calc(100vw - 32px);",
    "height:min(640px,calc(100vh - 40px));background:var(--bg);border-radius:var(--radius);",
    "box-shadow:var(--shadow);display:flex;flex-direction:column;overflow:hidden;",
    "border:1px solid var(--line)}",
    ".panel.right{right:20px}.panel.left{left:20px}",
    ".panel[hidden]{display:none}",

    ".head{display:flex;align-items:flex-start;gap:12px;padding:15px 16px;background:var(--green);color:#fff}",
    ".head h2{margin:0;font-size:15.5px;font-weight:650;letter-spacing:-.01em}",
    ".head p{margin:2px 0 0;font-size:12.5px;opacity:.82}",
    ".head .spacer{flex:1}",
    ".iconbtn{border:0;background:rgba(255,255,255,.14);color:#fff;width:30px;height:30px;",
    "border-radius:8px;cursor:pointer;font-size:15px;line-height:1;display:grid;place-items:center}",
    ".iconbtn:hover{background:rgba(255,255,255,.26)}",
    ".iconbtn:focus-visible{outline:2px solid var(--amber);outline-offset:2px}",

    ".log{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:14px;",
    "scroll-behavior:smooth;overscroll-behavior:contain}",
    "@media (prefers-reduced-motion:reduce){.log{scroll-behavior:auto}}",

    ".msg{max-width:92%;white-space:pre-wrap;word-wrap:break-word}",
    ".msg.user{align-self:flex-end;background:var(--green);color:#fff;padding:10px 13px;",
    "border-radius:14px 14px 4px 14px;max-width:85%}",
    ".msg.ai{align-self:flex-start}",
    ".msg.ai p{margin:0 0 9px}.msg.ai p:last-child{margin-bottom:0}",
    ".msg.ai strong{font-weight:650}",
    ".msg.ai ul,.msg.ai ol{margin:0 0 9px;padding-left:20px}",
    ".msg.ai h3{font-size:14.5px;font-weight:650;margin:13px 0 5px}",
    ".msg.ai h3:first-child{margin-top:0}",

    ".notice{align-self:flex-start;font-size:12.5px;color:var(--ink-soft);background:var(--bg-soft);",
    "border-left:3px solid var(--amber);padding:7px 11px;border-radius:0 8px 8px 0;max-width:92%}",

    ".cards{align-self:flex-start;display:flex;flex-direction:column;gap:8px;width:92%}",
    ".card{display:block;text-decoration:none;color:inherit;border:1px solid var(--line);",
    "border-radius:11px;padding:10px 12px;background:var(--bg-soft)}",
    ".card:hover{border-color:var(--green-bright);background:#eef3ee}",
    ".card:focus-visible{outline:2px solid var(--green-bright);outline-offset:2px}",
    ".card .t{font-weight:600;font-size:13.5px;line-height:1.35}",
    ".card .m{font-size:11.5px;color:var(--ink-soft);margin-top:3px}",
    ".card.aff{border-color:#e8d9a8;background:#fffaec}",
    ".card.aff:hover{border-color:var(--amber);background:#fff6e0}",
    ".tag{display:inline-block;font-size:10.5px;font-weight:650;letter-spacing:.02em;",
    "background:var(--amber);color:#3a2b00;padding:1px 6px;border-radius:4px;margin-right:6px}",

    ".fb{align-self:flex-start;display:flex;align-items:center;gap:6px;font-size:12px;color:var(--ink-soft)}",
    ".fb button{border:1px solid var(--line);background:var(--bg);border-radius:7px;padding:3px 9px;",
    "cursor:pointer;font:inherit;font-size:12px;color:var(--ink-soft)}",
    ".fb button:hover{border-color:var(--green-bright);color:var(--green)}",
    ".fb button:focus-visible{outline:2px solid var(--green-bright);outline-offset:1px}",
    ".fb button[aria-pressed='true']{background:var(--green);color:#fff;border-color:var(--green)}",
    ".fb .reasons{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}",

    ".starters{display:flex;flex-direction:column;gap:7px;padding:2px 0}",
    ".starter{text-align:left;border:1px solid var(--line);background:var(--bg);border-radius:10px;",
    "padding:9px 12px;cursor:pointer;font:inherit;font-size:13.5px;color:var(--ink)}",
    ".starter:hover{border-color:var(--green-bright);background:var(--bg-soft)}",
    ".starter:focus-visible{outline:2px solid var(--green-bright);outline-offset:1px}",

    ".dots{display:inline-flex;gap:4px;align-items:center;padding:4px 0}",
    ".dots i{width:6px;height:6px;border-radius:50%;background:var(--ink-soft);opacity:.45;",
    "animation:b 1.3s infinite ease-in-out}",
    ".dots i:nth-child(2){animation-delay:.18s}.dots i:nth-child(3){animation-delay:.36s}",
    "@keyframes b{0%,70%,100%{transform:translateY(0);opacity:.4}35%{transform:translateY(-4px);opacity:.9}}",
    "@media (prefers-reduced-motion:reduce){.dots i{animation:none}}",

    ".foot{border-top:1px solid var(--line);padding:11px 12px 12px;background:var(--bg)}",
    ".row{display:flex;gap:8px;align-items:flex-end}",
    "textarea{flex:1;resize:none;border:1px solid var(--line);border-radius:11px;padding:10px 12px;",
    "font:inherit;font-size:14.5px;color:var(--ink);background:var(--bg);max-height:120px;min-height:42px;",
    "line-height:1.45;font-family:inherit}",
    "textarea:focus{outline:2px solid var(--green-bright);outline-offset:-1px;border-color:transparent}",
    ".send{border:0;background:var(--green);color:#fff;border-radius:11px;width:42px;height:42px;",
    "cursor:pointer;font-size:17px;display:grid;place-items:center;flex:none}",
    ".send:hover:not(:disabled){background:var(--green-bright)}",
    ".send:disabled{opacity:.42;cursor:not-allowed}",
    ".send:focus-visible{outline:2px solid var(--amber);outline-offset:2px}",
    ".ai-note{font-size:11px;color:var(--ink-soft);margin:8px 2px 0;line-height:1.4}",
    ".sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;",
    "clip:rect(0,0,0,0);white-space:nowrap;border:0}",

    "@media (max-width:480px){",
    ".panel{right:0!important;left:0!important;bottom:0;width:100%;max-width:100%;height:88vh;",
    "height:88dvh;border-radius:var(--radius) var(--radius) 0 0;border-bottom:0}",
    ".launcher{bottom:14px}.launcher.right{right:14px}.launcher.left{left:14px}",
    "}"
  ].join("");

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  /**
   * Minimal, escaping-first markdown. The model returns light markdown
   * (bold, bullets, small headings) and nothing else is rendered — no raw
   * HTML path exists, so a model output cannot inject markup into the host
   * page.
   */
  function render(markdown) {
    var esc = markdown
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

    var lines = esc.split("\n");
    var html = "";
    var list = null;

    function closeList() {
      if (list) { html += "</" + list + ">"; list = null; }
    }

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var trimmed = line.trim();

      if (!trimmed) { closeList(); continue; }

      var heading = trimmed.match(/^#{1,4}\s+(.*)$/);
      if (heading) { closeList(); html += "<h3>" + inline(heading[1]) + "</h3>"; continue; }

      var bullet = trimmed.match(/^[-*•]\s+(.*)$/);
      if (bullet) {
        if (list !== "ul") { closeList(); html += "<ul>"; list = "ul"; }
        html += "<li>" + inline(bullet[1]) + "</li>";
        continue;
      }

      var ordered = trimmed.match(/^\d+[.)]\s+(.*)$/);
      if (ordered) {
        if (list !== "ol") { closeList(); html += "<ol>"; list = "ol"; }
        html += "<li>" + inline(ordered[1]) + "</li>";
        continue;
      }

      closeList();
      html += "<p>" + inline(trimmed) + "</p>";
    }
    closeList();
    return html;
  }

  function inline(text) {
    return text
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  }

  function Widget(options) {
    this.o = Object.assign({}, DEFAULTS, options || {});
    this.t = STRINGS[this.o.locale] || STRINGS.en;
    this.sessionId = this.loadSession();
    this.conversationId = null;
    this.busy = false;
    this.open = false;
    this.build();
    if (this.o.openOnLoad) this.toggle(true);
  }

  Widget.prototype.loadSession = function () {
    try {
      var existing = window.localStorage.getItem("cm_ai_session");
      if (existing) return existing;
      var fresh = (window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID().replace(/-/g, "")
        : String(Date.now()) + Math.random().toString(16).slice(2);
      window.localStorage.setItem("cm_ai_session", fresh);
      return fresh;
    } catch (e) {
      // Private mode, or storage blocked by consent. The session simply does
      // not persist across page loads; the chat still works.
      return null;
    }
  };

  Widget.prototype.build = function () {
    var host = el("div");
    host.setAttribute("data-comemorocco-ai", "");
    document.body.appendChild(host);
    var root = host.attachShadow({ mode: "open" });

    var style = document.createElement("style");
    style.textContent = CSS;
    root.appendChild(style);

    var side = this.o.position === "left" ? "left" : "right";

    var launcher = el("button", "launcher " + side);
    launcher.type = "button";
    launcher.appendChild(el("span", "flag", "\uD83C\uDDF2\uD83C\uDDE6"));
    launcher.appendChild(el("span", null, this.t.open));
    launcher.setAttribute("aria-haspopup", "dialog");
    launcher.setAttribute("aria-expanded", "false");

    var panel = el("div", "panel " + side);
    panel.hidden = true;
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "false");
    panel.setAttribute("aria-label", this.t.title);

    var head = el("div", "head");
    var titles = el("div");
    var h2 = el("h2", null, this.t.title);
    titles.appendChild(h2);
    titles.appendChild(el("p", null, this.t.subtitle));
    head.appendChild(titles);
    head.appendChild(el("div", "spacer"));

    var restart = el("button", "iconbtn", "\u21BB");
    restart.type = "button";
    restart.title = this.t.restart;
    restart.setAttribute("aria-label", this.t.restart);

    var close = el("button", "iconbtn", "\u00D7");
    close.type = "button";
    close.title = this.t.close;
    close.setAttribute("aria-label", this.t.close);

    head.appendChild(restart);
    head.appendChild(close);

    var log = el("div", "log");
    log.setAttribute("role", "log");
    // "polite" so a screen reader announces answers without interrupting, and
    // additions only so the whole thread is not re-read on every token.
    log.setAttribute("aria-live", "polite");
    log.setAttribute("aria-relevant", "additions");
    log.tabIndex = 0;

    var foot = el("div", "foot");
    var row = el("div", "row");
    var input = document.createElement("textarea");
    input.rows = 1;
    input.placeholder = this.t.placeholder;
    input.setAttribute("aria-label", this.t.placeholder);
    input.maxLength = 2000;

    var send = el("button", "send", "\u2191");
    send.type = "button";
    send.setAttribute("aria-label", this.t.send);
    send.disabled = true;

    row.appendChild(input);
    row.appendChild(send);
    foot.appendChild(row);
    foot.appendChild(el("p", "ai-note", this.t.aiNotice));

    panel.appendChild(head);
    panel.appendChild(log);
    panel.appendChild(foot);
    root.appendChild(launcher);
    root.appendChild(panel);

    this.root = root;
    this.launcher = launcher;
    this.panel = panel;
    this.log = log;
    this.input = input;
    this.sendBtn = send;

    var self = this;
    launcher.addEventListener("click", function () { self.toggle(true); });
    close.addEventListener("click", function () { self.toggle(false); });
    restart.addEventListener("click", function () { self.reset(); });

    input.addEventListener("input", function () {
      send.disabled = !input.value.trim() || self.busy;
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 120) + "px";
    });
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        self.submit();
      }
    });
    send.addEventListener("click", function () { self.submit(); });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && self.open) self.toggle(false);
    });
  };

  Widget.prototype.toggle = function (open) {
    this.open = open;
    this.panel.hidden = !open;
    this.launcher.style.display = open ? "none" : "inline-flex";
    this.launcher.setAttribute("aria-expanded", String(open));
    if (open) {
      this.track("chat_opened");
      if (!this.log.childElementCount) this.showStarters();
      this.input.focus();
    } else {
      this.track("chat_closed");
      this.launcher.focus();
    }
  };

  Widget.prototype.reset = function () {
    this.conversationId = null;
    this.log.innerHTML = "";
    this.showStarters();
    this.input.focus();
  };

  Widget.prototype.showStarters = function () {
    var self = this;
    var intro = el("div", "msg ai");
    intro.innerHTML = render(
      this.o.greeting ||
      (this.o.locale === "fr"
        ? "Dites-moi ce que vous préparez — la durée, avec qui vous voyagez — et je vous aide à partir de là."
        : "Tell me what you're planning — how long you have, who's travelling — and I can help from there.")
    );
    this.log.appendChild(intro);

    var wrap = el("div", "starters");
    fetch(this.o.apiBase + "/api/starters?lang=" + encodeURIComponent(this.o.locale), {
      headers: this.headers()
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        (data.starters || []).slice(0, 4).forEach(function (text) {
          var button = el("button", "starter", text);
          button.type = "button";
          button.addEventListener("click", function () {
            self.track("starter_question_clicked");
            self.ask(text);
            wrap.remove();
          });
          wrap.appendChild(button);
        });
      })
      .catch(function () { /* starters are optional */ });
    this.log.appendChild(wrap);
  };

  Widget.prototype.headers = function () {
    var headers = { "Content-Type": "application/json" };
    if (this.o.widgetKey) headers["X-Widget-Key"] = this.o.widgetKey;
    return headers;
  };

  Widget.prototype.submit = function () {
    var text = this.input.value.trim();
    if (!text || this.busy) return;
    this.input.value = "";
    this.input.style.height = "auto";
    this.ask(text);
  };

  Widget.prototype.scroll = function () {
    this.log.scrollTop = this.log.scrollHeight;
  };

  Widget.prototype.ask = function (text) {
    var self = this;
    this.busy = true;
    this.sendBtn.disabled = true;

    var mine = el("div", "msg user", text);
    this.log.appendChild(mine);

    var answer = el("div", "msg ai");
    var dots = el("div", "dots");
    dots.appendChild(el("i")); dots.appendChild(el("i")); dots.appendChild(el("i"));
    answer.appendChild(dots);
    this.log.appendChild(answer);
    this.scroll();

    var buffer = "";
    var meta = null;

    fetch(this.o.apiBase + "/api/chat/stream", {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({
        message: text,
        session_id: this.sessionId,
        conversation_id: this.conversationId,
        page_url: window.location.href,
        page_title: document.title,
        locale: this.o.locale
      })
    })
      .then(function (response) {
        if (!response.ok || !response.body) throw new Error("http " + response.status);

        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var pending = "";

        function pump() {
          return reader.read().then(function (chunk) {
            if (chunk.done) return self.finish(answer, buffer, meta);
            pending += decoder.decode(chunk.value, { stream: true });

            var blocks = pending.split("\n\n");
            pending = blocks.pop();

            blocks.forEach(function (block) {
              var event = "message";
              var data = "";
              block.split("\n").forEach(function (line) {
                if (line.indexOf("event:") === 0) event = line.slice(6).trim();
                else if (line.indexOf("data:") === 0) data += line.slice(5).trim();
              });
              if (!data) return;

              var payload;
              try { payload = JSON.parse(data); } catch (e) { return; }

              if (event === "meta") {
                meta = payload;
                self.conversationId = payload.conversation_id;
              } else if (event === "delta") {
                if (dots.parentNode) dots.remove();
                buffer += payload.text;
                answer.innerHTML = render(buffer);
                self.scroll();
              } else if (event === "done") {
                self.messageId = payload.message_id;
              } else if (event === "error") {
                buffer = payload.answer || self.t.error;
                answer.innerHTML = render(buffer);
              }
            });
            return pump();
          });
        }
        return pump();
      })
      .catch(function () {
        if (dots.parentNode) dots.remove();
        answer.innerHTML = render(self.t.error);
        self.release();
      });
  };

  Widget.prototype.finish = function (answer, buffer, meta) {
    if (!buffer) answer.innerHTML = render(this.t.error);

    if (meta) {
      (meta.notices || []).forEach(function (notice) {
        this.log.appendChild(el("div", "notice", notice));
      }, this);

      var resources = meta.resources || [];
      var affiliates = meta.affiliates || [];
      if (resources.length || affiliates.length) {
        var cards = el("div", "cards");
        var self = this;

        resources.forEach(function (resource) {
          var card = document.createElement("a");
          card.className = "card";
          card.href = resource.url;
          card.target = "_blank";
          card.rel = "noopener";
          var title = el("div", "t", resource.title);
          var metaLine = el("div", "m", self.t.readMore);
          card.appendChild(title);
          card.appendChild(metaLine);
          card.addEventListener("click", function () {
            self.track("link_clicked", { content_id: resource.content_id, url: resource.url });
          });
          cards.appendChild(card);
        });

        affiliates.forEach(function (affiliate) {
          var card = document.createElement("a");
          card.className = "card aff";
          card.href = affiliate.url;
          card.target = "_blank";
          // sponsored + nofollow: required for paid links, and the right
          // signal to search engines regardless of disclosure text.
          card.rel = "noopener sponsored nofollow";
          var title = el("div", "t");
          title.appendChild(el("span", "tag", self.t.disclosure));
          title.appendChild(document.createTextNode(affiliate.label || affiliate.name));
          card.appendChild(title);
          card.appendChild(el("div", "m", affiliate.disclosure));
          card.addEventListener("click", function () {
            self.track("affiliate_link_clicked", {
              affiliate_id: affiliate.affiliate_id, category: affiliate.category
            });
          });
          cards.appendChild(card);
        });
        this.log.appendChild(cards);
      }
    }

    this.appendFeedback();
    this.release();
    this.scroll();
  };

  Widget.prototype.appendFeedback = function () {
    if (!this.messageId) return;
    var self = this;
    var messageId = this.messageId;

    var wrap = el("div", "fb");
    var row = el("div");
    row.style.display = "flex";
    row.style.gap = "6px";
    row.style.alignItems = "center";

    var up = el("button", null, "\uD83D\uDC4D " + this.t.helpful);
    up.type = "button";
    up.setAttribute("aria-pressed", "false");
    var down = el("button", null, "\uD83D\uDC4E " + this.t.notHelpful);
    down.type = "button";
    down.setAttribute("aria-pressed", "false");

    row.appendChild(up);
    row.appendChild(down);
    wrap.appendChild(row);

    up.addEventListener("click", function () {
      up.setAttribute("aria-pressed", "true");
      down.disabled = true;
      self.feedback(messageId, true, null);
      wrap.replaceChildren(el("span", null, self.t.thanks));
    });

    down.addEventListener("click", function () {
      down.setAttribute("aria-pressed", "true");
      up.disabled = true;
      var reasons = el("div", "reasons");
      Object.keys(self.t.reasons).forEach(function (key) {
        var button = el("button", null, self.t.reasons[key]);
        button.type = "button";
        button.addEventListener("click", function () {
          self.feedback(messageId, false, key);
          wrap.replaceChildren(el("span", null, self.t.thanks));
        });
        reasons.appendChild(button);
      });
      wrap.appendChild(el("div", null, self.t.whatWrong));
      wrap.appendChild(reasons);
      self.scroll();
    });

    this.log.appendChild(wrap);
  };

  Widget.prototype.feedback = function (messageId, helpful, reason) {
    fetch(this.o.apiBase + "/api/feedback", {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ message_id: messageId, helpful: helpful, reason: reason })
    }).catch(function () { /* feedback is best-effort */ });
  };

  Widget.prototype.track = function (name, properties) {
    fetch(this.o.apiBase + "/api/events", {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({
        name: name,
        session_id: this.sessionId,
        conversation_id: this.conversationId,
        message_id: this.messageId || null,
        properties: properties || {}
      })
    }).catch(function () { /* analytics must never break the chat */ });
  };

  Widget.prototype.release = function () {
    this.busy = false;
    this.sendBtn.disabled = !this.input.value.trim();
  };

  window.ComeMoroccoAI = {
    init: function (options) {
      if (window.__cmAiWidget) return window.__cmAiWidget;
      window.__cmAiWidget = new Widget(options);
      return window.__cmAiWidget;
    }
  };

  // Auto-init from the script tag's data attributes, so the WordPress plugin
  // can enqueue one file with no inline bootstrap.
  var current = document.currentScript;
  if (current && current.dataset && current.dataset.apiBase) {
    var boot = {
      apiBase: current.dataset.apiBase,
      widgetKey: current.dataset.widgetKey || null,
      position: current.dataset.position || "right",
      locale: current.dataset.locale || DEFAULTS.locale,
      greeting: current.dataset.greeting || null
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () { window.ComeMoroccoAI.init(boot); });
    } else {
      window.ComeMoroccoAI.init(boot);
    }
  }
})();
