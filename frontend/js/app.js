import { fetchWithAuth, apiBase } from './api.js';
import { loginWithGoogle, logoutUser, initAuth, auth } from './auth.js';
import { items, currentPage, currentSearchParams, loadItems, loadMyItems, changePage, getItemDisplayData, deleteItem, compressImage } from './items.js';
import {
  currentProposalTargetId, currentMypageTrades, _currentChatTradeId, _chatSocket, _currentRatingTradeId, _currentRatingScore,
  openProposalModal, closeProposalModal, toggleProposalType, updateProposalPreview, submitProposal,
  openRatingModal, closeRatingModal, clearRatingModal, setRatingStars, submitRating,
  updateTradeStatus, openChatModal, closeChatModal, loadChatMessages, renderChatMessages,
  sendChatMessage, completeTrade, completeChatTrade,
  loadIncomingTrades, loadChatIncomingTrades, loadChatOutgoingTrades,
  renderChatIncomingTrades, renderChatOutgoingTrades, renderOutgoingTrades, renderIncomingTrades
} from './trade.js';

// ==========================================
// グローバルブリッジ（HTMLのonclickから呼ぶため）
// ==========================================
window.apiBase = apiBase;
window.fetchWithAuth = fetchWithAuth;
window.auth = auth; 
window.items = items;
window.currentPage = currentPage;
window.currentSearchParams = currentSearchParams;
window.loadItems = loadItems;
window.loadMyItems = loadMyItems;
window.changePage = changePage;
window.getItemDisplayData = getItemDisplayData;
window.deleteItem = deleteItem;
window.compressImage = compressImage;
window.openProposalModal = openProposalModal;
window.closeProposalModal = closeProposalModal;
window.toggleProposalType = toggleProposalType;
window.updateProposalPreview = updateProposalPreview;
window.submitProposal = submitProposal;
window.openRatingModal = openRatingModal;
window.closeRatingModal = closeRatingModal;
window.clearRatingModal = clearRatingModal;
window.setRatingStars = setRatingStars;
window.submitRating = submitRating;
window.updateTradeStatus = updateTradeStatus;
window.openChatModal = openChatModal;
window.closeChatModal = closeChatModal;
window.loadChatMessages = loadChatMessages;
window.renderChatMessages = renderChatMessages;
window.sendChatMessage = sendChatMessage;
window.completeTrade = completeTrade;
window.completeChatTrade = completeChatTrade;
window.loadIncomingTrades = loadIncomingTrades;
window.loadChatIncomingTrades = loadChatIncomingTrades;
window.loadChatOutgoingTrades = loadChatOutgoingTrades;
window.renderChatIncomingTrades = renderChatIncomingTrades;
window.renderChatOutgoingTrades = renderChatOutgoingTrades;
window.renderOutgoingTrades = renderOutgoingTrades;
window.renderIncomingTrades = renderIncomingTrades;
window.currentMypageTrades = currentMypageTrades;
window._currentChatTradeId = _currentChatTradeId;
window._chatSocket = _chatSocket;

// ==========================================
// 認証の初期化とログイン・ログアウト制御
// ==========================================
initAuth(async (dbUser, firebaseUser) => {
  window.currentUserData = dbUser; 
  if (typeof window.updateAuthUI === 'function') window.updateAuthUI();
  if (typeof window.loadItems === 'function') await window.loadItems();
});

window.handleGoogleLogin = async () => {
  try {
    await loginWithGoogle();
    if (typeof window.closeLoginModal === 'function') window.closeLoginModal();
  } catch (error) {
    console.error(error);
    alert("ログインをキャンセルしました、または失敗しました。");
  }
};

window.signOutUser = async function() {
  await logoutUser();
};

// ==========================================
// UI・画面制御ロジック
// ==========================================
let mypageActiveTab = 'available';
let editingItemId = null;
let currentReportTargetId = null;

window.updateAuthUI = function() {
  const guest = document.getElementById('auth-guest');
  const userEl = document.getElementById('auth-user');
  const name = document.getElementById('auth-name');
  if (window.currentUserData) {
    if (guest) { guest.classList.remove('flex'); guest.classList.add('hidden'); }
    if (userEl) { userEl.classList.remove('hidden'); userEl.classList.add('flex'); }
    if (name) name.textContent = `${window.currentUserData.name} さん`;
  } else {
    if (guest) { guest.classList.remove('hidden'); guest.classList.add('flex'); }
    if (userEl) { userEl.classList.remove('flex'); userEl.classList.add('hidden'); }
    if (name) name.textContent = '';
  }
};

window.renderPagination = function(meta) {
  const controls = document.getElementById('pagination-controls');
  const label = document.getElementById('pagination-label');
  const prev = document.getElementById('pagination-prev');
  const next = document.getElementById('pagination-next');
  if (!controls || !label || !prev || !next) return;
  const currentPage = meta?.current_page || 1;
  const totalPages = meta?.total_pages || 1;
  label.textContent = `${currentPage} / ${totalPages} ページ`;
  prev.disabled = currentPage <= 1;
  next.disabled = currentPage >= totalPages;
  controls.classList.toggle('hidden', totalPages <= 1);
};

window.renderItems = function(list) {
  const grid = document.getElementById('items-grid');
  if (!grid) return;
  if (!list.length) {
    grid.innerHTML = '<div class="col-span-2 text-center text-gray-500">該当するアイテムがありません。</div>';
    return;
  }
  grid.innerHTML = list.map(item => `
    <article onclick="window.openModal('${window.escapeHtml(item.id)}')" class="bg-white rounded-lg shadow-sm overflow-hidden cursor-pointer">
      <div class="aspect-[4/3] bg-gray-100 flex items-center justify-center text-gray-400">
        <img src="${window.escapeHtml(item.imageUrl)}" alt="${window.escapeHtml(item.characterName)}" class="object-cover w-full h-full" onerror="this.src='https://placehold.jp/e0e0e0/888888/400x300.png?text=No+Image'" />
      </div>
      <div class="p-3">
        <div class="text-sm text-gray-500">シリーズ: ${window.escapeHtml(item.seriesName)}</div>
        <div class="font-medium">キャラクター: ${window.escapeHtml(item.characterName)}</div>
        <div class="mt-2 flex flex-wrap items-center gap-2">
          <span class="text-xs px-2 py-1 rounded-full ${item.exchangeMethod === '手渡し' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'}">${window.escapeHtml(item.exchangeMethod)}</span>
        </div>
      </div>
    </article>
  `).join('');
};

window.openLoginModal = function() {
  const modal = document.getElementById('login-modal');
  if (!modal) return;
  const agreeCheckbox = document.getElementById('login-agree-checkbox');
  const loginButton = document.getElementById('login-google-btn');
  if (agreeCheckbox) agreeCheckbox.checked = false;
  if (loginButton) loginButton.disabled = true;
  modal.classList.remove('hidden');
  modal.classList.add('flex');
};
window.closeLoginModal = function() {
  const modal = document.getElementById('login-modal');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.classList.remove('flex');
};

window.openEditItemModal = function(itemId) {
  if (!window.currentUserData) return window.openLoginModal();
  const item = window.items.find(it => it.id === itemId);
  if (!item) return alert('アイテム情報が取得できませんでした。');
  
  editingItemId = itemId;
  const seriesInput = document.getElementById('edit-series');
  const characterInput = document.getElementById('edit-character');
  const methodSelect = document.getElementById('edit-method');
  const placeInput = document.getElementById('edit-place');

  if (seriesInput) seriesInput.value = item.seriesName || item.series_name || '';
  if (characterInput) characterInput.value = item.characterName || item.character_name || '';
  if (methodSelect) methodSelect.value = item.exchangeMethod || item.exchange_method || '手渡し';
  if (placeInput) placeInput.value = item.handoverPlace || item.handover_place || '';
  window.toggleEditPlaceInput();

  const modal = document.getElementById('edit-item-modal');
  if (modal) { modal.classList.remove('hidden'); modal.classList.add('flex'); }
};
window.closeEditItemModal = function() {
  const modal = document.getElementById('edit-item-modal');
  if (modal) { modal.classList.add('hidden'); modal.classList.remove('flex'); }
  editingItemId = null;
};
window.toggleEditPlaceInput = function() {
  const method = document.getElementById('edit-method')?.value;
  const placeWrap = document.getElementById('edit-place-wrap');
  if (!placeWrap) return;
  if (method === '手渡し') placeWrap.classList.remove('hidden');
  else placeWrap.classList.add('hidden');
};

window.submitEditItem = async function() {
  if (!editingItemId) return alert('編集対象のアイテムが見つかりません。');
  const seriesInput = document.getElementById('edit-series');
  const characterInput = document.getElementById('edit-character');
  const methodSelect = document.getElementById('edit-method');
  const placeInput = document.getElementById('edit-place');
  
  const seriesName = seriesInput.value.trim();
  const characterName = characterInput.value.trim();
  const exchangeMethod = methodSelect.value;
  const handoverPlace = placeInput?.value.trim() || null;

  if (!seriesName || !characterName) return alert('必須項目を入力してください。');

  const submitBtn = document.getElementById('edit-item-submit');
  if (submitBtn) { submitBtn.textContent = '保存中...'; submitBtn.disabled = true; }

  try {
    const res = await window.fetchWithAuth(`/items/${editingItemId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        series_name: seriesName,
        character_name: characterName,
        exchange_method: exchangeMethod,
        handover_place: exchangeMethod === '手渡し' ? handoverPlace : null,
      }),
    });
    if (!res.ok) throw new Error('編集の保存に失敗しました。');
    window.closeEditItemModal();
    alert('アイテム情報を更新しました。');
    if (typeof window.loadItems === 'function') await window.loadItems();
    if (typeof window.loadMyItems === 'function') await window.loadMyItems();
  } catch (err) {
    alert(err.message || '編集の保存に失敗しました。');
  } finally {
    if (submitBtn) { submitBtn.textContent = '保存する'; submitBtn.disabled = false; }
  }
};

window.openReportModal = function(itemId) {
  if (!window.currentUserData) return window.openLoginModal();
  currentReportTargetId = itemId;
  const modal = document.getElementById('report-modal');
  if (!modal) return;
  document.getElementById('report-reason').value = 'スパム';
  document.getElementById('report-details').value = '';
  modal.classList.remove('hidden');
  modal.classList.add('flex');
};
window.closeReportModal = function() {
  const modal = document.getElementById('report-modal');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.classList.remove('flex');
  currentReportTargetId = null;
};
window.submitReport = async function() {
  if (!currentReportTargetId) return alert('通報対象のアイテムが設定されていません。');
  const reason = document.getElementById('report-reason').value;
  const details = document.getElementById('report-details').value.trim();
  const payload = {
    reported_item_id: currentReportTargetId,
    reason: details ? `${reason} - ${details}` : reason,
  };
  const submitBtn = document.getElementById('report-submit');
  if (submitBtn) { submitBtn.textContent = '送信中...'; submitBtn.disabled = true; }
  try {
    const res = await window.fetchWithAuth('/reports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('通報の送信に失敗しました');
    window.closeReportModal();
    alert('通報を受け付けました。運営で確認いたします。');
  } catch (err) {
    alert(err.message || '通報の送信に失敗しました');
  } finally {
    if (submitBtn) { submitBtn.textContent = '送信する'; submitBtn.disabled = false; }
  }
};

window.updateMypageRatingUI = function() {
  const label = document.getElementById('mypage-rating-label');
  const count = document.getElementById('mypage-rating-count');
  if (!label || !count) return;
  const average = window.currentUserData?.average_rating;
  const ratingCount = window.currentUserData?.rating_count ?? 0;
  if (ratingCount > 0 && typeof average === 'number') {
    label.textContent = `★ ${average.toFixed(1)}`;
    count.textContent = `(${ratingCount}件)`;
  } else {
    label.textContent = '評価なし';
    count.textContent = '';
  }
};
window.fetchCurrentUser = async function() {
  try {
    const res = await window.fetchWithAuth('/users/me');
    if (!res.ok) throw new Error('取得失敗');
    window.currentUserData = await res.json();
    window.updateAuthUI();
    if (typeof window.updateMypageRatingUI === 'function') window.updateMypageRatingUI();
  } catch (err) {}
};

window.openProfileEditModal = function() {
  if (!window.currentUserData) return window.openLoginModal();
  const nameInput = document.getElementById('profile-name');
  const prefectureInput = document.getElementById('profile-prefecture');
  if (nameInput) nameInput.value = window.currentUserData.name || '';
  if (prefectureInput) prefectureInput.value = window.currentUserData.prefecture || '';
  const modal = document.getElementById('profile-modal');
  if (modal) { modal.classList.remove('hidden'); modal.classList.add('flex'); }
};
window.closeProfileModal = function() {
  const modal = document.getElementById('profile-modal');
  if (modal) { modal.classList.add('hidden'); modal.classList.remove('flex'); }
};
window.submitProfileUpdate = async function() {
  if (!window.currentUserData) return window.openLoginModal();
  const name = document.getElementById('profile-name').value.trim();
  const prefecture = document.getElementById('profile-prefecture').value;
  if (!name || !prefecture) return alert('必須項目を入力してください。');

  const saveBtn = document.getElementById('profile-save');
  if (saveBtn) { saveBtn.textContent = '保存中...'; saveBtn.disabled = true; }
  try {
    const res = await window.fetchWithAuth('/users/me', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, prefecture }),
    });
    if (!res.ok) throw new Error('更新失敗');
    window.currentUserData = await res.json();
    window.updateAuthUI();
    window.showMyPage();
    window.closeProfileModal();
    alert('プロフィールを更新しました。');
  } catch (error) {
    alert('プロフィールの更新に失敗しました。');
  } finally {
    if (saveBtn) { saveBtn.textContent = '保存する'; saveBtn.disabled = false; }
  }
};

window.loadCatalog = async function() {
  try {
    const res = await window.fetchWithAuth('/zukan/pairs');
    if (!res.ok) throw new Error('取得失敗');
    const pairs = await res.json();
    const map = new Map();
    (pairs || []).forEach(p => {
      const s = p.series_name || '未設定';
      const c = p.character_name || '';
      if (!map.has(s)) map.set(s, new Set());
      if (c) map.get(s).add(c);
    });
    const groups = Array.from(map.entries()).map(([series, set]) => ({ series, characters: Array.from(set) }));
    window.renderCatalog(groups);
  } catch (err) {
    window.renderCatalog([]);
  }
};
window.renderCatalog = function(groups) {
  const wrap = document.getElementById('zukan-list');
  if (!wrap) return;
  if (!groups || !groups.length) {
    wrap.innerHTML = '<div class="text-sm text-gray-500">図鑑データがありません。</div>';
    return;
  }
  wrap.innerHTML = groups.map(g => `
    <div class="bg-white p-4 rounded-lg shadow-sm">
      <div class="flex items-center justify-between">
        <h3 class="font-semibold">${window.escapeHtml(g.series)}</h3>
        <span class="text-xs text-gray-500">${window.escapeHtml(g.characters.length)} キャラクター</span>
      </div>
      <div class="mt-3 flex flex-wrap gap-2">
        ${g.characters.map(ch => `<span class="text-sm px-2 py-1 rounded-full bg-yellow-50 text-yellow-800">${window.escapeHtml(ch)}</span>`).join('')}
      </div>
    </div>
  `).join('');
};

window.openModal = function(id) {
  const modal = document.getElementById('item-modal');
  const item = window.items.find(it => it.id === id);
  if (!item) return;
  document.getElementById('modal-image').src = item.imageUrl;
  document.getElementById('modal-series').textContent = 'シリーズ: ' + item.seriesName;
  document.getElementById('modal-character').textContent = 'キャラクター: ' + item.characterName;
  
  const applyBtn = document.getElementById('modal-apply');
  applyBtn.onclick = () => window.openProposalModal(item.id);
  
  document.getElementById('modal-close').onclick = () => {
    modal.classList.add('hidden'); modal.classList.remove('flex');
  };
  
  const reportBtn = document.getElementById('item-report-button');
  if(reportBtn) reportBtn.onclick = () => window.openReportModal(item.id);

  modal.classList.remove('hidden'); modal.classList.add('flex');
};

window.openWithdrawModal = function() {
  const modal = document.getElementById('withdraw-modal');
  if (modal) { modal.classList.remove('hidden'); modal.classList.add('flex'); }
};
window.closeWithdrawModal = function() {
  const modal = document.getElementById('withdraw-modal');
  if (modal) { modal.classList.add('hidden'); modal.classList.remove('flex'); }
};

window.executeWithdraw = async function() {
  const btn = document.getElementById('withdraw-confirm');
  try {
    if (btn) { btn.disabled = true; btn.textContent = '処理中...'; }
    const res = await window.fetchWithAuth('/users/me', { method: 'DELETE' });
    if (!res.ok) throw new Error('退会処理に失敗しました。');
    if (typeof window.signOutUser === 'function') await window.signOutUser();
    window.currentUserData = null;
    alert('退会が完了しました。ご利用ありがとうございました。');
    window.closeWithdrawModal();
    window.location.reload();
  } catch (err) {
    alert(err.message || '退会処理に失敗しました。');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '退会を実行する'; }
  }
};

window.showHome = function() {
  document.getElementById('home-area').classList.remove('hidden');
  document.getElementById('mypage-area').classList.add('hidden');
  document.getElementById('chat-area').classList.add('hidden');
  document.getElementById('zukan-area').classList.add('hidden');
};

window.showMyPage = function() {
  document.getElementById('home-area').classList.add('hidden');
  document.getElementById('mypage-area').classList.remove('hidden');
  document.getElementById('chat-area').classList.add('hidden');
  document.getElementById('zukan-area').classList.add('hidden');
  
  const name = document.getElementById('mypage-name');
  const pref = document.getElementById('mypage-pref');
  if(window.currentUserData) {
    name.textContent = window.currentUserData.name;
    pref.textContent = window.currentUserData.prefecture + "在住";
  }
  window.updateMypageAvatarUI();
  window.updateMypageRatingUI();
  if (typeof window.loadItems === 'function') window.loadItems();
  window.renderMyPageList();
  if (typeof window.loadIncomingTrades === 'function') window.loadIncomingTrades();
  if (typeof window.loadOutgoingTrades === 'function') window.loadOutgoingTrades(); 
};

window.showChat = function() {
  document.getElementById('home-area').classList.add('hidden');
  document.getElementById('mypage-area').classList.add('hidden');
  document.getElementById('chat-area').classList.remove('hidden');
  document.getElementById('zukan-area').classList.add('hidden');
  if (typeof window.loadChatIncomingTrades === 'function') window.loadChatIncomingTrades();
  if (typeof window.loadChatOutgoingTrades === 'function') window.loadChatOutgoingTrades();
};

window.setMypageTab = function(tab) {
  mypageActiveTab = tab;
  ['available', 'trading', 'completed'].forEach(key => {
    const btn = document.getElementById(`mypage-tab-${key}`);
    if (!btn) return;
    if (key === tab) {
      btn.classList.add('border-red-500', 'text-red-600');
      btn.classList.remove('border-transparent', 'text-gray-600');
    } else {
      btn.classList.remove('border-red-500', 'text-red-600');
      btn.classList.add('border-transparent', 'text-gray-600');
    }
  });
  window.renderMyPageList();
};

window.updateMypageAvatarUI = function() {
  const avatarImg = document.getElementById('mypage-avatar-img');
  const avatarLetter = document.getElementById('mypage-avatar-letter');
  if (!avatarImg || !avatarLetter) return;

  if (window.currentUserData?.avatar_url) {
    avatarImg.src = window.currentUserData.avatar_url;
    avatarImg.classList.remove('hidden');
    avatarLetter.classList.add('hidden');
  } else {
    avatarImg.classList.add('hidden');
    avatarLetter.classList.remove('hidden');
    avatarLetter.textContent = window.currentUserData?.name?.trim().charAt(0).toUpperCase() || 'U';
  }
};

window.openAvatarPicker = function() {
  if (!window.currentUserData) return window.openLoginModal();
  const input = document.getElementById('avatar-file-input');
  if (input) input.click();
};

window.onAvatarFileChange = async function() {
  const input = document.getElementById('avatar-file-input');
  if (!input || !input.files?.length) return;
  const file = input.files[0];
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await window.fetchWithAuth('/users/me/avatar', {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('失敗');
    window.currentUserData = await res.json();
    if (typeof window.updateAuthUI === 'function') window.updateAuthUI();
    window.updateMypageAvatarUI();
    alert('プロフィール画像を更新しました。');
  } catch (err) {
    alert('アバターのアップロードに失敗しました。');
  } finally {
    input.value = '';
  }
};

window.showZukan = function() {
  document.getElementById('home-area').classList.add('hidden');
  document.getElementById('mypage-area').classList.add('hidden');
  document.getElementById('chat-area').classList.add('hidden');
  document.getElementById('zukan-area').classList.remove('hidden');
  if (typeof window.loadCatalog === 'function') window.loadCatalog();
};

window.renderMyPageList = function() {
  const listWrap = document.getElementById('mypage-list');
  if (!listWrap) return;
  const myItems = window.items ? window.items.filter(it => it.isMine) : [];
  const incoming = window.currentMypageTrades?.incoming || [];
  const outgoing = window.currentMypageTrades?.outgoing || [];
  const tradingIds = new Set();
  const completedIds = new Set();

  incoming.forEach(trade => {
    if (trade.status === 'completed') completedIds.add(trade.item_id);
    else if (trade.status === 'accepted' || trade.status === 'pending') tradingIds.add(trade.item_id);
  });
  outgoing.forEach(trade => {
    if (!trade.proposed_item_id) return;
    if (trade.status === 'completed') completedIds.add(trade.proposed_item_id);
    else if (trade.status === 'accepted' || trade.status === 'pending') tradingIds.add(trade.proposed_item_id);
  });

  const mineItems = myItems.filter(item => {
    if (mypageActiveTab === 'available') return item.status === 'available' && !tradingIds.has(item.id) && !completedIds.has(item.id);
    if (mypageActiveTab === 'trading') return tradingIds.has(item.id) || item.status === 'trading';
    if (mypageActiveTab === 'completed') return completedIds.has(item.id) || item.status === 'completed' || item.status === 'traded';
    return false;
  });

  if (!mineItems.length) {
    listWrap.innerHTML = `<div class="text-center text-gray-500">アイテムはありません。</div>`;
    return;
  }
  listWrap.innerHTML = mineItems.map(item => {
    const statusLabel = item.status === 'available' ? '出品中' : item.status === 'trading' ? '交換中' : item.status === 'completed' ? '完了' : item.status === 'traded' ? '取引済み' : window.escapeHtml(item.status);
    const isWithdrawable = item.status === 'available';
    return `
      <div class="flex items-center gap-3 p-3 border rounded-lg hover:bg-gray-50">
        <img src="${window.escapeHtml(item.imageUrl)}" alt="" class="w-20 h-20 rounded-xl object-cover" />
        <div class="flex-1 min-w-0">
          <div class="font-semibold text-sm truncate">${window.escapeHtml(item.characterName)}</div>
          <div class="text-xs text-gray-500 truncate">${window.escapeHtml(item.seriesName)}</div>
        </div>
        <div class="text-right flex flex-col items-end gap-2">
          <span class="text-xs px-2 py-1 rounded-full ${item.status === 'available' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-700'}">${statusLabel}</span>
          ${isWithdrawable ? `
            <div class="flex items-center gap-2">
              <button type="button" onclick="window.openEditItemModal('${window.escapeHtml(item.id)}')" class="inline-flex items-center gap-2 text-gray-700 border border-gray-200 hover:bg-gray-50 px-3 py-1 rounded-full text-xs"><i class="fa-solid fa-pen-to-square"></i> 編集</button>
              <button type="button" onclick="window.deleteItem('${window.escapeHtml(item.id)}')" class="inline-flex items-center gap-2 text-red-600 border border-red-200 hover:bg-red-50 px-3 py-1 rounded-full text-xs"><i class="fa-solid fa-trash"></i> 取り下げ</button>
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }).join('');
};

window.escapeHtml = function(str) {
  if(!str) return '';
  return String(str).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
};

window.handleImagePreview = function(inputElement, previewImgId) {
  const f = inputElement.files[0];
  if (f) {
    const r = new FileReader();
    r.onload = function(e) {
      const img = document.getElementById(previewImgId);
      if (img) { img.src = e.target.result; img.classList.remove('hidden'); }
    };
    r.readAsDataURL(f);
  }
};

// ==========================================
// イベントリスナーの登録
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
  window.updateAuthUI();
  const searchForm = document.getElementById('search-form');
  if (searchForm) {
    searchForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const query = document.getElementById('q').value.trim();
      const prefecture = document.getElementById('search-prefecture').value;
      window.loadItems({ series_name: query, prefecture });
    });
  }

  const loginAgreeCheckbox = document.getElementById('login-agree-checkbox');
  const loginGoogleBtn = document.getElementById('login-google-btn');
  if (loginAgreeCheckbox && loginGoogleBtn) {
    loginAgreeCheckbox.addEventListener('change', () => {
      loginGoogleBtn.disabled = !loginAgreeCheckbox.checked;
    });
  }

  const listSubmit = document.getElementById('list-submit');
  if(listSubmit) {
    listSubmit.addEventListener('click', async () => {
      if(!window.currentUserData) return window.openLoginModal();
      const series = document.getElementById('list-series').value.trim();
      const character = document.getElementById('list-character').value.trim();
      const exchange = document.getElementById('list-method').value;
      const place = document.getElementById('list-place').value.trim();
      const condition = document.getElementById('list-condition').value;
      const fileInput = document.getElementById('list-file');
      
      if (!condition) return alert('商品の状態を選択してください。');
      if (!fileInput.files.length) return alert('出品にはアイテムの写真が1枚必要です。');

      listSubmit.textContent = "画像圧縮中...";
      listSubmit.disabled = true;

      const compressedFile = await window.compressImage(fileInput.files[0]);

      listSubmit.textContent = "出品中...";
      const formData = new FormData();
      formData.append('series_name', series);
      formData.append('character_name', character);
      formData.append('exchange_method', exchange);
      formData.append('handover_place', exchange === '手渡し' ? place : '');
      formData.append('condition', condition);
      formData.append('status', 'available');
      formData.append('file', compressedFile);
      
      try {
        const res = await window.fetchWithAuth('/items/', { method: 'POST', body: formData });
        if (!res.ok) throw new Error('出品に失敗しました');
        alert('出品が完了しました！');
        document.getElementById('list-modal').classList.add('hidden');
        document.getElementById('list-modal').classList.remove('flex');
        await window.loadItems();
      } catch (err) {
        alert('出品に失敗しました。');
      } finally {
        listSubmit.textContent = "出品する";
        listSubmit.disabled = false;
      }
    });
  }
  
  document.getElementById('nav-home').onclick = (e) => { e.preventDefault(); window.showHome(); };
  document.getElementById('nav-chat').onclick = (e) => { e.preventDefault(); if(!window.currentUserData) return window.openLoginModal(); window.showChat(); };
  document.getElementById('nav-mypage').onclick = (e) => { 
    e.preventDefault(); 
    if(!window.currentUserData) return window.openLoginModal();
    window.showMyPage(); 
  };
  document.getElementById('nav-list').onclick = (e) => {
    e.preventDefault();
    if(!window.currentUserData) return window.openLoginModal();
    document.getElementById('list-modal').classList.remove('hidden');
    document.getElementById('list-modal').classList.add('flex');
  };
  document.getElementById('nav-zukan').onclick = (e) => { e.preventDefault(); window.showZukan(); };
  
  document.getElementById('list-close').onclick = () => {
    document.getElementById('list-modal').classList.add('hidden');
    document.getElementById('list-modal').classList.remove('flex');
  };
  document.getElementById('list-cancel').onclick = document.getElementById('list-close').onclick;

  const proposalClose = document.getElementById('proposal-close');
  if (proposalClose) proposalClose.onclick = window.closeProposalModal;
  const mypageAvailable = document.getElementById('mypage-tab-available');
  const mypageTrading = document.getElementById('mypage-tab-trading');
  const mypageCompleted = document.getElementById('mypage-tab-completed');
  if (mypageAvailable) mypageAvailable.onclick = () => window.setMypageTab('available');
  if (mypageTrading) mypageTrading.onclick = () => window.setMypageTab('trading');
  if (mypageCompleted) mypageCompleted.onclick = () => window.setMypageTab('completed');
  const proposalCancel = document.getElementById('proposal-cancel');
  if (proposalCancel) proposalCancel.onclick = window.closeProposalModal;
  const proposalSubmit = document.getElementById('proposal-submit');
  if (proposalSubmit) proposalSubmit.onclick = window.submitProposal;

  const editProfileBtn = document.getElementById('edit-profile-btn');
  if (editProfileBtn) editProfileBtn.addEventListener('click', (e) => { e.preventDefault(); window.openProfileEditModal(); });
  const profileClose = document.getElementById('profile-close');
  if (profileClose) profileClose.onclick = window.closeProfileModal;
  const profileCancel = document.getElementById('profile-cancel');
  if (profileCancel) profileCancel.onclick = window.closeProfileModal;
  const profileSave = document.getElementById('profile-save');
  if (profileSave) profileSave.onclick = window.submitProfileUpdate;

  const openWithdrawBtn = document.getElementById('open-withdraw-btn');
  if (openWithdrawBtn) openWithdrawBtn.addEventListener('click', (e) => { e.preventDefault(); window.openWithdrawModal(); });
  const withdrawClose = document.getElementById('withdraw-close');
  if (withdrawClose) withdrawClose.onclick = window.closeWithdrawModal;
  const withdrawCancel = document.getElementById('withdraw-cancel');
  if (withdrawCancel) withdrawCancel.onclick = window.closeWithdrawModal;
  const withdrawConfirm = document.getElementById('withdraw-confirm');
  if (withdrawConfirm) withdrawConfirm.onclick = window.executeWithdraw;
  
  const chatClose = document.getElementById('chat-close');
  if (chatClose) chatClose.onclick = window.closeChatModal;
  const chatSend = document.getElementById('chat-send');
  if (chatSend) chatSend.onclick = window.sendChatMessage;
  const chatComplete = document.getElementById('chat-complete');
  if (chatComplete) chatComplete.onclick = window.completeChatTrade;
  const chatInput = document.getElementById('chat-input');
  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); window.sendChatMessage(); }
    });
  }
  const ratingStarButtons = document.querySelectorAll('#rating-stars .rating-star');
  ratingStarButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const score = Number(button.dataset.score || 0);
      if (score) window.setRatingStars(score);
    });
  });
  
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      await logoutUser();
      alert('ログアウトしました。');
      if (typeof window.showHome === 'function') window.showHome();
    });
  }
});

// ==========================================
// 通知センター
// ==========================================
(function() {
  let _notifications = [];
  function renderNotifItem(n) {
    const unreadClass = n.is_read ? 'bg-white' : 'bg-yellow-50 border-l-4 border-yellow-400';
    const timeStr = n.created_at ? new Date(n.created_at).toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
    const typeIcon = { trade_request: '🔔', trade_update: '🔄', info: 'ℹ️' }[n.type] || '📢';
    return `
      <div class="rounded-lg px-3 py-2 ${unreadClass} cursor-pointer hover:bg-yellow-100 transition-colors"
           onclick="window.readNotif('${window.escapeHtml(n.id)}', this)">
        <div class="flex items-start gap-2">
          <span class="text-base mt-0.5">${typeIcon}</span>
          <div class="flex-1 min-w-0">
            <div class="text-xs font-semibold text-gray-800 truncate">${window.escapeHtml(n.title)}</div>
            <div class="text-xs text-gray-600 mt-0.5 whitespace-pre-wrap break-words">${window.escapeHtml(n.message)}</div>
            <div class="text-xs text-gray-400 mt-1">${timeStr}</div>
          </div>
          ${!n.is_read ? '<span class="w-2 h-2 rounded-full bg-red-500 mt-1 flex-shrink-0"></span>' : ''}
        </div>
      </div>
    `;
  }

  function renderNotifLists() {
    const globalList = document.getElementById('notif-global-list');
    const personalList = document.getElementById('notif-personal-list');
    if (!globalList || !personalList) return;
    const globals = _notifications.filter(n => n.user_id === null || n.user_id === undefined);
    const personals = _notifications.filter(n => n.user_id != null);
    globalList.innerHTML = globals.length ? globals.map(renderNotifItem).join('') : '<div class="text-sm text-gray-400 py-2">お知らせはありません</div>';
    personalList.innerHTML = personals.length ? personals.map(renderNotifItem).join('') : '<div class="text-sm text-gray-400 py-2">通知はありません</div>';
  }

  function updateBadge() {
    const badge = document.getElementById('notif-badge');
    if (!badge) return;
    const unread = _notifications.filter(n => !n.is_read).length;
    if (unread > 0) {
      badge.textContent = unread > 99 ? '99+' : String(unread);
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  }

  window.loadNotifications = async function() {
    if (!window.currentUserData) return;
    try {
      const res = await window.fetchWithAuth('/notifications/');
      if (!res.ok) return;
      _notifications = await res.json();
      renderNotifLists();
      updateBadge();
    } catch (e) {}
  };

  window.readNotif = async function(id, el) {
    const notif = _notifications.find(n => n.id === id);
    if (!notif || notif.is_read) return;
    try {
      await window.fetchWithAuth(`/notifications/${id}/read`, { method: 'PATCH' });
      notif.is_read = true;
      renderNotifLists();
      updateBadge();
    } catch (e) {}
  };

  window.markAllRead = async function() {
    if (!window.currentUserData) return;
    try {
      await window.fetchWithAuth('/notifications/read-all', { method: 'PATCH' });
      _notifications.forEach(n => { n.is_read = true; });
      renderNotifLists();
      updateBadge();
    } catch (e) {}
  };

  window.openNotifDrawer = function() {
    const drawer = document.getElementById('notif-drawer');
    const overlay = document.getElementById('notif-overlay');
    if (!drawer || !overlay) return;
    overlay.classList.remove('hidden');
    drawer.classList.remove('translate-x-full');
    window.loadNotifications();
  };

  window.closeNotifDrawer = function() {
    const drawer = document.getElementById('notif-drawer');
    const overlay = document.getElementById('notif-overlay');
    if (!drawer || !overlay) return;
    drawer.classList.add('translate-x-full');
    overlay.classList.add('hidden');
  };

  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('notif-btn');
    if (btn) btn.addEventListener('click', window.openNotifDrawer);
  });
})();

const _origUpdateAuthUI = window.updateAuthUI;
window.updateAuthUI = function() {
  if (_origUpdateAuthUI) _origUpdateAuthUI.apply(this, arguments);
  window.loadNotifications && window.loadNotifications();
};