import { fetchWithAuth } from './api.js';

export let items = [];
export let currentPage = 1;
export let currentSearchParams = { series_name: '', prefecture: '' };

export async function loadItems(params = {}) {
  try {
    if ('series_name' in params) {
      currentSearchParams.series_name = params.series_name || '';
      currentPage = 1;
    }
    if ('prefecture' in params) {
      currentSearchParams.prefecture = params.prefecture || '';
      currentPage = 1;
    }
    if ('page' in params) {
      currentPage = Number(params.page) || 1;
    }

    const qs = new URLSearchParams();
    if (currentSearchParams.series_name) qs.append('series_name', currentSearchParams.series_name);
    if (currentSearchParams.prefecture) qs.append('prefecture', currentSearchParams.prefecture);
    qs.append('page', String(currentPage));
    
    const res = await fetchWithAuth(`/items/?${qs.toString()}`);
    if (!res.ok) throw new Error('アイテムの取得に失敗しました。');

    const data = await res.json();
    const rawItems = (data.data || []);
    const meta = data.meta || { current_page: currentPage, total_pages: 1 };

    items = rawItems.map(item => getItemDisplayData(item));
    window.items = items; // グローバル変数と同期

    if (typeof window.renderItems === 'function') window.renderItems(items);
    if (typeof window.renderMyPageList === 'function') window.renderMyPageList();
    if (typeof window.renderPagination === 'function') window.renderPagination(meta);
  } catch (err) {
    console.warn(err);
    if (typeof window.renderItems === 'function') window.renderItems([]);
    if (typeof window.renderPagination === 'function') window.renderPagination({ current_page: currentPage, total_pages: 1 });
  }
}

export async function loadMyItems() {
  await loadItems();
}

export async function changePage(delta) {
  const nextPage = Math.max(1, currentPage + delta);
  if (nextPage === currentPage) return;
  currentPage = nextPage;
  await loadItems({ page: currentPage });
}

export function getItemDisplayData(item) {
  return {
    ...item,
    seriesName: item.series_name,
    characterName: item.character_name,
    exchangeMethod: item.exchange_method || '手渡し',
    handoverPlace: item.handover_place || '',
    imageUrl: item.image_url || item.image_front_url || `https://placehold.jp/e0e0e0/888888/400x300.png?text=No+Image`,
    status: item.status,
    ownerId: item.owner_id,
    prefecture: item.prefecture || '',
    isMine: window.currentUserData ? (item.owner_id === window.currentUserData.id) : false,
  };
}

export async function deleteItem(itemId) {
  if (!confirm('本当にこの出品を取り下げますか？')) return;
  try {
    const res = await fetchWithAuth(`/items/${itemId}`, { method: 'DELETE' });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || '取り下げに失敗しました');
    }
    alert('出品を取り下げました。');
    await loadItems();
  } catch (err) {
    alert(err.message || '取り下げに失敗しました');
  }
}

export async function compressImage(file, maxWidth = 1200, quality = 0.8) {
  if (!file || !file.type.startsWith('image/')) return file;
  
  const dataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('読み込み失敗'));
    reader.readAsDataURL(file);
  });
  
  const image = await new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('読み込み失敗'));
    img.src = dataUrl;
  });
  
  const ratio = Math.min(1, maxWidth / image.width);
  const width = Math.round(image.width * ratio);
  const height = Math.round(image.height * ratio);
  const canvas = document.createElement('canvas');
  canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (ctx) ctx.drawImage(image, 0, 0, width, height);
  
  const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', quality));
  if (!blob) return file;
  
  const filename = file.name || 'image.jpg';
  const jpgName = filename.includes('.') ? filename.replace(/\.[^.]+$/, '.jpg') : `${filename}.jpg`;
  return new File([blob], jpgName, { type: 'image/jpeg' });
}