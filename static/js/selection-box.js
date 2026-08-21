(function(){
    const SelectionBox = {
        el: null,
        init(selector = '#selectionBox'){
            if(!this.el) this.el = document.querySelector(selector);
            if(!this.el){
                this.el = document.createElement('div');
                this.el.className = 'selection-box';
                document.body.appendChild(this.el);
            }
            return this.el;
        },
        update(sx, sy, x, y){
            const el = this.init();
            el.style.display = 'block';
            el.style.left = `${Math.min(sx, x)}px`;
            el.style.top = `${Math.min(sy, y)}px`;
            el.style.width = `${Math.abs(x - sx)}px`;
            el.style.height = `${Math.abs(y - sy)}px`;
            return el;
        },
        hide(){
            if(this.el) this.el.style.display = 'none';
        }
    };
    window.SelectionBox = SelectionBox;
})();
