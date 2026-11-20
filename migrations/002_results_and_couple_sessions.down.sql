-- 002 geri alma. Uyarı: yeni sonuçları ve açık çift oturumlarını siler.
BEGIN;
DROP TABLE IF EXISTS couple_sessions;
DROP TABLE IF EXISTS results;
COMMIT;
