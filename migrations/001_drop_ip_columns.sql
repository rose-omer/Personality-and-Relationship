-- 001: KVKK. Eski tablolardaki IP sütunlarını kaldırır.
-- Geri alınamaz: silinen IP verisi geri gelmez (bilerek "down" dosyası yok).
-- Tablo ya da sütun yoksa hata vermez; birden çok kez çalıştırılabilir.
BEGIN;
ALTER TABLE IF EXISTS test_results DROP COLUMN IF EXISTS ip_address;
ALTER TABLE IF EXISTS couple_test_results DROP COLUMN IF EXISTS user1_ip;
ALTER TABLE IF EXISTS couple_test_results DROP COLUMN IF EXISTS user2_ip;
COMMIT;
