const assert = require('node:assert/strict');
const fs = require('node:fs');

const source = fs.readFileSync('static/js/canvas-list.js', 'utf8');
const start = source.indexOf("document.addEventListener('keydown', e => {");
const end = source.indexOf('// language switch from parent', start);
assert.ok(start >= 0 && end > start, 'keyboard handler not found');
const binding = source.slice(start, end);

function keyboardHandler({selectedIds = new Set(), undoItems = [], editing = false} = {}){
    let handler;
    const calls = {deleteIds:null, undo:0, closeMenu:0, closeCreate:0};
    const listener = new Function(
        'document', 'trashPanel', 'undoDeleteCanvases', 'canvasMutationPending', 'selectedIds',
        'closeCardMenu', 'closeCreateCard', 'boardWorld', 'deleteCanvases', 'undoLastCanvasDelete',
        'canvases', 'startCardRename',
        binding
    );
    listener(
        {addEventListener:(type, callback) => { if(type === 'keydown') handler = callback; }},
        {classList:{contains:() => false}}, undoItems, false, selectedIds,
        () => { calls.closeMenu += 1; }, () => { calls.closeCreate += 1; },
        {querySelectorAll:() => []}, ids => { calls.deleteIds = ids; }, () => { calls.undo += 1; },
        [], () => {}
    );
    return {
        calls,
        press(key, options = {}){
            const event = {
                key, code:options.code || key, ctrlKey:Boolean(options.ctrlKey), metaKey:false, shiftKey:false,
                target:editing ? {closest:() => ({})} : {closest:() => null, isContentEditable:false},
                preventDefault(){ this.defaultPrevented = true; }
            };
            handler(event);
            return event;
        }
    };
}

let test = keyboardHandler({selectedIds:new Set(['one', 'two'])});
assert.equal(test.press('Delete').defaultPrevented, true);
assert.deepEqual(test.calls.deleteIds, ['one', 'two']);
assert.equal(test.calls.closeMenu, 1);
assert.equal(test.calls.closeCreate, 1);

test = keyboardHandler({undoItems:[{id:'one'}]});
assert.equal(test.press('z', {ctrlKey:true}).defaultPrevented, true);
assert.equal(test.calls.undo, 1);

test = keyboardHandler({selectedIds:new Set(['one']), editing:true});
assert.equal(test.press('Delete').defaultPrevented, undefined);
assert.equal(test.calls.deleteIds, null);

console.log('canvas-list keyboard delete/undo: ok');
