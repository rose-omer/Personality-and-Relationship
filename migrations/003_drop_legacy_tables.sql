-- 003 (isteğe bağlı): Eski tabloları siler. Uygulama bu tabloları artık okumaz ve yazmaz.
-- Çalıştırmadan önce yedek al ve verinin taşınmayacağına karar ver. Geri alınamaz.
BEGIN;
DROP TABLE IF EXISTS couple_test_results;
DROP TABLE IF EXISTS test_results;
COMMIT;
