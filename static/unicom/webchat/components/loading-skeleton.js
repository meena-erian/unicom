import {html} from 'lit';

const stylesheet = new URL('../loading-skeleton.css', import.meta.url).href;

// Keep visual rules in the same stylesheet used before JavaScript boots.
export function loadingSkeleton(label = 'Loading conversation') {
  return html`<link rel="stylesheet" href=${stylesheet}>
    <div class="unicom-loading-skeleton" role="status" aria-label=${label}>
      <span aria-hidden="true"></span><span aria-hidden="true"></span><span aria-hidden="true"></span>
    </div>`;
}
