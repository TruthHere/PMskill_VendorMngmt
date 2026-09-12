(function (global) {
  'use strict';

  var DEBOUNCE_MS = 500;
  var saveTimer = null;
  var editMode = true;
  var hasUnsavedChanges = false;
  var lastSavedAt = null;

  function $(id) {
    return document.getElementById(id);
  }

  function getPageId() {
    return document.body.getAttribute('data-page-id') || '';
  }

  function hasServerSave() {
    return document.body.getAttribute('data-save-mode') === 'server';
  }

  function getToolbar() {
    return document.querySelector('.edit-toolbar');
  }

  function setStatus(state, text) {
    var status = $('editStatus');
    if (!status) return;
    status.classList.remove('saving', 'error', 'offline');
    if (state) status.classList.add(state);
    var label = status.querySelector('.status-text');
    if (label) label.textContent = text;
  }

  function isBlockedElement(el) {
    if (!el || el.nodeType !== 1) return true;
    var tag = el.tagName;
    if (tag === 'BUTTON' || tag === 'INPUT' || tag === 'SCRIPT' || tag === 'STYLE') return true;
    if (el.closest('.edit-toolbar')) return true;
    return false;
  }

  function selectorMatchesElement(el, selector) {
    try {
      return el.matches(selector);
    } catch (e) {
      return false;
    }
  }

  function hasEditableDescendant(el, selectors) {
    for (var i = 0; i < selectors.length; i++) {
      var children = el.querySelectorAll(selectors[i]);
      for (var j = 0; j < children.length; j++) {
        if (children[j] !== el && !isBlockedElement(children[j])) {
          return true;
        }
      }
    }
    return false;
  }

  function makeEditable(selectors) {
    var root = document.querySelector('#editable-root');
    if (!root) return;

    selectors.forEach(function (selector) {
      root.querySelectorAll(selector).forEach(function (el) {
        if (isBlockedElement(el)) return;
        if (hasEditableDescendant(el, selectors)) return;
        if (el.hasAttribute('contenteditable')) return;
        el.setAttribute('contenteditable', 'true');
        el.setAttribute('data-editable', 'true');
      });
    });
  }

  function setEditMode(enabled) {
    editMode = enabled;
    document.body.classList.toggle('edit-mode', enabled);

    var btn = $('editToggle');
    var resetBtn = $('resetBtn');
    if (btn) {
      btn.textContent = enabled ? '✏️ 编辑模式：开' : '👁️ 编辑模式：关';
      btn.classList.toggle('off', !enabled);
    }
    if (resetBtn) {
      resetBtn.style.display = enabled ? 'none' : 'inline-block';
    }

    document.querySelectorAll('[data-editable="true"]').forEach(function (el) {
      el.setAttribute('contenteditable', enabled ? 'true' : 'false');
    });
  }

  function toggleEdit() {
    setEditMode(!editMode);
  }

  function buildPersistableHtml() {
    var clone = document.documentElement.cloneNode(true);

    clone.querySelectorAll('[contenteditable]').forEach(function (el) {
      el.removeAttribute('contenteditable');
    });
    clone.querySelectorAll('[data-editable]').forEach(function (el) {
      el.removeAttribute('data-editable');
    });

    var status = clone.querySelector('#editStatus');
    if (status) {
      status.classList.remove('saving', 'error', 'offline');
      var label = status.querySelector('.status-text');
      if (label) label.textContent = '自动保存已开启';
    }

    var html = clone.outerHTML;
    if (!html.startsWith('<!DOCTYPE html>')) {
      html = '<!DOCTYPE html>\n' + html;
    }
    return html;
  }

  function markDirty() {
    hasUnsavedChanges = true;
    setStatus('saving', '保存中...');
  }

  function markSaved() {
    hasUnsavedChanges = false;
    lastSavedAt = new Date();
    var time = lastSavedAt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    setStatus('', '已保存 ' + time);
  }

  function markError(message) {
    setStatus('error', message || '保存失败');
  }

  function saveToServer() {
    var pageId = getPageId();
    if (!pageId) {
      markError('缺少 page-id');
      return Promise.reject(new Error('missing page id'));
    }

    return fetch('/api/save/' + encodeURIComponent(pageId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html: buildPersistableHtml() }),
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().catch(function () {
            return { error: res.statusText };
          }).then(function (payload) {
            throw new Error(payload.error || '保存失败');
          });
        }
        return res.json();
      })
      .then(function () {
        markSaved();
      })
      .catch(function (err) {
        markError(err.message || '保存失败');
        throw err;
      });
  }

  function downloadHtml() {
    var blob = new Blob([buildPersistableHtml()], { type: 'text/html;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = getPageId() || 'document.html';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setStatus('offline', '已导出文件，请手动替换原文件');
  }

  function saveNow() {
    if (hasServerSave()) {
      return saveToServer();
    }
    downloadHtml();
    return Promise.resolve();
  }

  function debounceSave() {
    if (!editMode) return;
    markDirty();
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(function () {
      saveNow().catch(function () {});
    }, DEBOUNCE_MS);
  }

  function resetPage() {
    if (!confirm('确定要重置吗？将重新加载页面，未保存的修改会丢失。')) return;
    if (hasServerSave()) {
      location.reload();
      return;
    }
    location.reload();
  }

  function bindEvents() {
    document.addEventListener('input', function (event) {
      if (!event.target.closest('#editable-root')) return;
      debounceSave();
    });

    document.addEventListener('focusout', function (event) {
      if (!event.target.closest('#editable-root')) return;
      if (!event.target.hasAttribute('data-editable')) return;
      debounceSave();
    });

    window.addEventListener('beforeunload', function (event) {
      if (!hasUnsavedChanges) return;
      event.preventDefault();
      event.returnValue = '';
    });
  }

  function init(options) {
    options = options || {};
    makeEditable(options.selectors || []);
    setEditMode(true);
    bindEvents();

    if (hasServerSave()) {
      setStatus('', '自动保存已开启');
    } else {
      setStatus('offline', '离线模式：请启动本地服务后编辑');
    }

    var saveBtn = $('saveNowBtn');
    if (saveBtn) {
      if (hasServerSave()) {
        saveBtn.style.display = 'none';
      } else {
        saveBtn.style.display = 'inline-block';
        saveBtn.textContent = '⬇️ 导出 HTML';
      }
    }
  }

  global.PMEditable = {
    init: init,
    toggleEdit: toggleEdit,
    saveNow: saveNow,
    resetPage: resetPage,
    setEditMode: setEditMode,
  };
})(window);
