/** Generic interaction host. Trusted presentation modules export a Web Component
 * class; each receives .state and may emit interaction-action with {action}.
 * Authentication, CSRF, errors and buttons remain owned by this host.
 */
import { LitElement, html, css } from 'lit';

const modules = new Map();
let sequence = 0;
async function loadComponent(path) {
  const url = new URL(path, window.location.origin);
  if (url.origin !== window.location.origin) throw new Error('Presentation must be same-origin');
  if (!modules.has(url.href)) {
    modules.set(url.href, import(url.href).then(module => {
      const name = `unicom-presentation-${++sequence}`;
      customElements.define(name, module.default);
      return name;
    }).catch(error => { modules.delete(url.href); throw error; }));
  }
  return modules.get(url.href);
}

export class ToolInteraction extends LitElement {
  static properties = { state: {type: Object}, busy: {state: true}, error: {state: true}, customFailed: {state: true} };
  static styles = css`
    :host { display:block; width:100%; max-width:580px; color:var(--unicom-text-color,#202735); }
    .card { border:1px solid var(--unicom-border-color,#e4e8ef); border-radius:18px; overflow:hidden; background:var(--unicom-message-bg-incoming,#f1f4f8); }
    .body { padding:20px; overflow-wrap:anywhere; }
    .custom:empty { display:none; }
    .fallback { margin:0; white-space:pre-wrap; }
    footer { padding:0 20px 18px; display:flex; flex-wrap:wrap; gap:10px; }
    button { font:inherit; padding:10px 16px; border-radius:10px; border:1px solid var(--unicom-border-color,#ddd); cursor:pointer; color:inherit; background:var(--unicom-background-color,#fff); }
    button.primary { background:var(--unicom-primary-color,#6750a4); color:var(--unicom-primary-foreground,#fff); }
    button.danger { color:#b42318; }
    button:disabled { opacity:.6; cursor:default; }
    button:focus-visible { outline:2px solid currentColor; outline-offset:3px; }
    .status,.error { font-size:.875em; padding:0 20px 16px; }
    .error { color:#b42318; }
  `;

  constructor() { super(); this.busy=false; this.error=''; this.customFailed=false; this._generation=0; }
  connectedCallback() {
    super.connectedCallback();
    this._resizeObserver = new ResizeObserver(() => {
      this.dispatchEvent(new CustomEvent('interaction-resize', {bubbles:true, composed:true}));
    });
    this._resizeObserver.observe(this);
    this.requestUpdate();
  }
  disconnectedCallback() { super.disconnectedCallback(); this._resizeObserver?.disconnect(); this._generation++; this._request?.abort(); clearTimeout(this._expiry); }

  updated(changed) {
    if (changed.has('state')) {
      const previous = changed.get('state');
      if (previous?.id !== this.state?.id || previous?.component?.module !== this.state?.component?.module) {
        this._generation++; this._loadingPath=null; this._componentPath=null; this.customFailed=false;
        this.renderRoot.querySelector('.custom')?.replaceChildren();
      }
      clearTimeout(this._expiry);
      const delay = new Date(this.state?.expiresAt).getTime() - Date.now();
      if (this.state?.status === 'awaiting_input' && delay > 0) {
        this._expiry = setTimeout(() => this.requestUpdate(), Math.min(delay + 20, 2147483647));
      }
    }
    this._updateComponent();
  }

  async _updateComponent() {
    const container = this.renderRoot.querySelector('.custom');
    const path = this.state?.component?.module;
    if (!container || !path) return;
    if (this._componentPath === path && container.firstElementChild) {
      try { container.firstElementChild.state = this.state; }
      catch { this.customFailed=true; this._componentPath=null; container.replaceChildren(); }

      return;
    }
    if (this._loadingPath === path || this.customFailed) return;
    this._loadingPath = path;
    const generation = ++this._generation;
    try {
      const name = await loadComponent(path);
      if (!this.isConnected || generation !== this._generation) return;
      const component = document.createElement(name);
      component.state = this.state;
      container.replaceChildren(component);
      this._componentPath = path;
      this.requestUpdate();
    } catch { this.customFailed=true; this._componentPath=null; container.replaceChildren(); }
    finally { this._loadingPath=null; }
  }

  async submit(action) {
    const button = this.state?.buttons?.find(button => button.action === action);
    if (this.busy || !button || this.state.status !== 'awaiting_input' || Date.parse(this.state.expiresAt) <= Date.now()) return;
    this.busy=true; this.error='';
    this._request = new AbortController();
    try {
      const csrf = document.cookie.split(';').map(item => item.trim()).find(item => item.startsWith('csrftoken='))?.slice(10) || '';
      const response = await fetch('/unicom/webchat/button-click/', {
        method:'POST', credentials:'same-origin', signal:this._request.signal,
        headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(csrf)},
        body:JSON.stringify({callback_execution_id:button.callback_execution_id}),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'Could not submit your choice. Please retry.');
      if (payload.interaction) this.state=payload.interaction;
      this.dispatchEvent(new CustomEvent('interaction-updated', {detail:this.state,bubbles:true,composed:true}));
    } catch(error) { if (error.name !== 'AbortError') this.error=error.message; }
    finally { this.busy=false; }
  }

  render() {
    if (!this.state) return html``;
    const expired = this.state.status === 'awaiting_input' && Date.parse(this.state.expiresAt) <= Date.now();
    const pending = this.state.status === 'awaiting_input' && !expired;
    const custom = this.state.component?.module && !this.customFailed;
    return html`<section class="card" aria-label="Tool interaction" aria-busy=${this.busy}>
      <div class="body">
        <div class="custom" @interaction-action=${event => {event.stopPropagation(); this.submit(event.detail?.action);}}></div>
        ${!custom || !this._componentPath ? html`<p class="fallback">${this.state.text}</p>` : ''}
      </div>
      ${pending ? html`<footer>${this.state.buttons.map(button => html`<button class=${button.style} ?disabled=${this.busy} @click=${() => this.submit(button.action)}>${button.text}</button>`)}</footer>` : html`<div class="status" role="status">${expired ? 'Expired' : this.state.status}</div>`}
      ${this.error ? html`<div class="error" role="alert">${this.error}</div>` : ''}
    </section>`;
  }
}
customElements.define('tool-interaction', ToolInteraction);
