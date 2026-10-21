// Buddy host integration. Upstream components retain their MIT license.
import React from "react";
import {createRoot} from "react-dom/client";
import {Renderer, createLibrary, defineComponent, type ActionEvent} from "@openuidev/react-lang";
import {z} from "zod/v4";
import {library as upstream} from "@/lib/library";
import {runLibraryAction} from "@/lib/actions";

// These components require APIs belonging to the upstream demo, execute HTML,
// or embed third-party pages. Buddy deliberately does not expose them.
const excluded = new Set(["SearchImage", "HtmlView", "YouTube", "Image"]);
const image = defineComponent({name:'Image',props:z.object({src:z.string(),alt:z.string(),aspectRatio:z.number().optional(),radius:z.union([z.string(),z.number()]).optional(),fit:z.enum(['cover','contain']).optional()}),
  component:({props})=> /^https:\/\//.test(props.src) ? <img src={props.src} alt={props.alt} referrerPolicy="no-referrer" style={{maxWidth:'100%',aspectRatio:props.aspectRatio,objectFit:props.fit||'cover',borderRadius:props.radius}}/> : <span>{props.alt}</span>});
const library = createLibrary({
  root: "Col", components: [...Object.values(upstream.components).filter(c => !excluded.has(c.name)),image],
  functions: Object.values(upstream.functions), actions: Object.values(upstream.actions),
});
const offline = library.extend!({components: {remove: ["Map", "MapMarker", "Image"]}});
const script = document.querySelector<HTMLScriptElement>('script[data-buddy-openui]')!;
const assets = new URL("./", script.src);
const config = JSON.parse(document.querySelector('#buddy-config')!.textContent!);
const selected = config.network ? library : offline;
const notify = (message: object) => parent.postMessage(message, config.origin);
function theme(dark: boolean) {
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
  document.documentElement.style.setProperty('--openui-text-neutral-primary', dark ? '#eeeeee' : '#0d0d0d');
  document.documentElement.style.color = dark ? '#eeeeee' : '#0d0d0d';
  document.documentElement.style.setProperty('--openui-text-neutral-secondary', dark ? '#aaaaaa' : '#606060');
  document.documentElement.style.setProperty('--openui-foreground', dark ? '#202020' : '#ffffff');
  document.documentElement.style.setProperty('--iui-on-ink', dark ? '#151515' : '#ffffff');
}
theme(matchMedia('(prefers-color-scheme: dark)').matches);
addEventListener('message', event => {
  if (event.source === parent && event.origin === config.origin && event.data?.type === 'buddy:theme' && typeof event.data.dark === 'boolean') theme(event.data.dark);
});
notify({type:'buddy:ready'});
const resize = () => notify({type:'iframe:height',height:Math.ceil(document.documentElement.scrollHeight)});
new ResizeObserver(resize).observe(document.body);
async function action(event: ActionEvent) {
  const custom = runLibraryAction(event); if (custom) {await custom;return;}
  if (event.type === 'open_url') {
    const url = new URL(String(event.params?.url || ''), config.origin);
    if (['https:', 'http:', 'mailto:', 'tel:'].includes(url.protocol)) window.open(url.href,'_blank','noopener,noreferrer');
    return;
  }
  if (event.type !== 'continue_conversation') return;
  let text = event.humanFriendlyMessage || '';
  if (event.formState && Object.keys(event.formState).length) text += '\n\n' + JSON.stringify(event.formState);
  if (event.params && Object.keys(event.params).length) text += '\n\n' + JSON.stringify(event.params);
  if (text.trim()) notify({type:'input:prompt:submit',text});
}
// A wrong argument (Title(text, "h2")) only drops that argument; the component still renders with its
// default, so its error would just be noise under a working answer. Show errors only when nothing rendered.
const errorBox=document.createElement('div');errorBox.setAttribute('role','alert');document.body.append(errorBox);
const view=document.createElement('div');view.id='buddy-root';view.style.cssText='font-family:var(--iui-font);color:var(--iui-ink);padding:8px';
document.querySelector('#buddy-root')!.replaceWith(view);
let errorText='';
const showIfEmpty=()=>{const rendered=view.textContent!.trim()||view.querySelector('svg,canvas,img,input,button');errorBox.textContent=rendered?'':errorText;resize();};
createRoot(view).render(<Renderer library={selected} response={config.code} isStreaming={false} onAction={action} publishObservability={false}
  onError={errors=>{errorText=errors.filter(e=>e.severity!=='warning').map(e=>e.message).join('; ');setTimeout(showIfEmpty,0);}}/>);
// Browser tests and optional manual inspection can query the exact shipped spec.
(window as any).__BuddyOpenUI = {library:selected,assets:assets.href};
