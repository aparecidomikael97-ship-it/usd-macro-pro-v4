from atlasquant_aion_platform_intent import detect_platform_intent,evaluate_platform_intent

def test_explicit_youtube_search_routes_read():
 r=detect_platform_intent("AION, procure no YouTube um vídeo sobre macroeconomia")
 assert r["matched"] and r["provider"]=="youtube" and r["action_class"]=="READ"

def test_spotify_playback_is_write_like_and_confirmation_gated():
 r=evaluate_platform_intent("AION, toque minha playlist no Spotify",{"spotify":True})
 assert r["provider"]=="spotify" and r["action_class"]=="WRITE"
 assert r["allowed"] and r["confirmation_required"] is True

def test_unconnected_platform_fails_closed():
 r=evaluate_platform_intent("Mostre meus vídeos do YouTube",{"youtube":False})
 assert not r["allowed"] and r["reason"]=="CONNECTOR_NOT_CONNECTED"

def test_generic_music_question_is_not_hijacked_by_spotify():
 r=detect_platform_intent("Como funciona harmonia em música?")
 assert r["matched"] is False
