const fs = require('fs');
const marked = require('marked');

function mdToHtml(inFile, outFile) {
    const md = fs.readFileSync(inFile, 'utf-8');
    const htmlContent = marked.parse(md);
    const html = `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; padding: 40px; max-width: 900px; margin: 0 auto; color: #333; }
            h1, h2, h3 { border-bottom: 1px solid #eaecef; padding-bottom: .3em; margin-top: 24px; margin-bottom: 16px; font-weight: 600; line-height: 1.25; color: #111; }
            code { background-color: rgba(27,31,35,.05); border-radius: 3px; font-size: 85%; margin: 0; padding: .2em .4em; font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, monospace; }
            pre { background-color: #f6f8fa; border-radius: 6px; font-size: 85%; line-height: 1.45; overflow: auto; padding: 16px; border: 1px solid #e1e4e8; }
            pre code { background-color: transparent; border: 0; display: inline; padding: 0; }
            table { border-collapse: collapse; width: 100%; margin-top: 0; margin-bottom: 16px; }
            table th, table td { border: 1px solid #dfe2e5; padding: 6px 13px; }
            table th { font-weight: 600; background-color: #f6f8fa; }
            table tr:nth-child(2n) { background-color: #f6f8fa; }
            a { color: #0366d6; text-decoration: none; }
            li { margin-bottom: 0.25em; }
        </style>
    </head>
    <body>
        ${htmlContent}
    </body>
    </html>
    `;
    fs.writeFileSync(outFile, html);
}

mdToHtml('PRD.md', 'PRD.html');
mdToHtml('TECHNICAL_ARCHITECTURE.md', 'TECHNICAL_ARCHITECTURE.html');
