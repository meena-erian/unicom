"""Run directly with Python + Playwright/Chromium; no Django or accounts needed."""
import functools
import http.server
from pathlib import Path
import threading


def main():
    from playwright.sync_api import sync_playwright
    root = Path(__file__).resolve().parents[1]
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            page.set_content('''<script type="importmap">{"imports":{"lit":"https://cdn.jsdelivr.net/npm/lit@3.2.0/+esm","lit/directives/unsafe-html.js":"https://cdn.jsdelivr.net/npm/lit@3.2.0/directives/unsafe-html.js/+esm"}}</script><div id="fixture" style="width:360px;height:500px"></div>''')
            page.evaluate('''async () => {
              await import('/static/unicom/webchat/components/message-list.js');
              await import('/static/unicom/webchat/components/chat-list.js');
              const fixture=document.querySelector('#fixture');
              for (const [tag,key,item] of [
                ['message-list','messages',{id:'one',text:'Keep this visible',is_outgoing:false,timestamp:new Date().toISOString()}],
                ['chat-list','chats',{id:'one',name:'Keep this visible'}]
              ]) {
                const element=document.createElement(tag);fixture.append(element);
                element.loading=true;await element.updateComplete;
                if(!element.shadowRoot.querySelector('.unicom-loading-skeleton')) throw Error(tag+' missing initial skeleton');
                element[key]=[item];element.loading=false;await element.updateComplete;
                const selector=tag==='message-list'?'message-item':'.chat-item';
                const original=element.shadowRoot.querySelector(selector);
                const top=original.getBoundingClientRect().top;
                for(let i=0;i<3;i++) {
                  element.loading=true;await element.updateComplete;
                  if(element.shadowRoot.querySelector('.unicom-loading-skeleton')) throw Error(tag+' refresh replaced content with skeleton');
                  if(original!==element.shadowRoot.querySelector(selector)) throw Error(tag+' replaced existing node');
                  if(original.getBoundingClientRect().top!==top) throw Error(tag+' refresh shifted content');
                  element.loading=false;await element.updateComplete;
                }
                element.remove();
              }
              const element=document.createElement('message-list');element.loading=true;fixture.append(element);
              await element.updateComplete;
            }''')
            page.wait_for_function("getComputedStyle(document.querySelector('message-list').shadowRoot.querySelector('.unicom-loading-skeleton > span'),'::after').animationName === 'unicom-skeleton-glare'")
            assert page.evaluate("getComputedStyle(document.querySelector('message-list').shadowRoot.querySelector('.unicom-loading-skeleton > span'),'::after').animationDuration") == '4s'
            page.emulate_media(reduced_motion='reduce')
            assert page.evaluate("getComputedStyle(document.querySelector('message-list').shadowRoot.querySelector('.unicom-loading-skeleton > span'),'::after').animationName") == 'none'
            browser.close()
        print('PASS: initial skeleton, stable refresh DOM/layout, slow glare, reduced motion')
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
