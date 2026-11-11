'use strict';
const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(process.argv[2]||'assessment-public');
const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.ico':'image/x-icon'};
if(!fs.existsSync(root))throw new Error('Publish directory not found: '+root);
const server=http.createServer((req,res)=>{
 let pathname;
 try{pathname=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname);}catch{res.writeHead(400);res.end('Bad request');return;}
 if(pathname==='/')pathname='/index.html';
 const target=path.resolve(root,'.'+pathname);
 if(target!==root&&!target.startsWith(root+path.sep)){res.writeHead(403);res.end('Forbidden');return;}
 let stat;try{stat=fs.statSync(target);}catch{res.writeHead(404);res.end('Not found');return;}
 if(!stat.isFile()){res.writeHead(404);res.end('Not found');return;}
 res.writeHead(200,{'Content-Type':mime[path.extname(target).toLowerCase()]||'application/octet-stream','Content-Length':stat.size,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
 if(req.method==='HEAD'){res.end();return;}fs.createReadStream(target).pipe(res);
});
server.listen(4173,'127.0.0.1',()=>process.stdout.write('Assessment site available at http://127.0.0.1:4173\n'));
