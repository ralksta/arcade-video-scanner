import React, {useState, useCallback, useEffect, useRef} from 'react';
import {serverUrl, posterUrl} from '../serverConfig';
import {getItem} from '../safeStorage';
import displayName from '../displayName';
import {getProgress, saveProgress} from '../watchProgress';
import ThemeDecorator from '@enact/limestone/ThemeDecorator';
import Panels from '@enact/limestone/Panels';
import VideoPlayer, {Video} from '@enact/limestone/VideoPlayer';
import Spotlight from '@enact/spotlight';
import SpotlightContainerDecorator from '@enact/spotlight/SpotlightContainerDecorator';

import MainPanel from '../views/MainPanel';
import LoginPanel from '../views/LoginPanel';
import css from './App.module.less';

// Der Player liegt als Ebene über der Hauptansicht, nicht als eigenes Panel:
// Limestones Panels halten nur das aktive Panel im Speicher. Nach jedem
// Video baute sich die Hauptansicht neu auf — zurück auf Home, Position weg,
// die ganze Bibliothek neu geladen. Der Fokus bleibt in der Ebene.
const PlayerLayer = SpotlightContainerDecorator({restrict: 'self-only'}, 'div');

const MAIN = 0;
const LOGIN = 1;

const App = (props) => {
	const existingToken = getItem('arcade_session_token');

	// Ohne Token direkt zum Login
	const [panelIndex, setPanelIndex] = useState(existingToken ? MAIN : LOGIN);
	const [activeVideo, setActiveVideo] = useState(null);
	// Zählt hoch, wenn die Bibliothek neu geladen werden soll (App kehrt aus
	// dem Hintergrund zurück).
	const [reloadKey, setReloadKey] = useState(0);

	// Ref, damit der Back-Handler den aktuellen Player sieht, ohne bei jeder
	// Änderung neu registriert zu werden; ebenso die Sicherungsfunktion.
	const activeVideoRef = useRef(null);
	const saveRef = useRef(() => {});
	// Kachel, von der aus abgespielt wurde — bekommt danach den Fokus zurück.
	const returnFocusRef = useRef(null);
	useEffect(() => {
		activeVideoRef.current = activeVideo;
	}, [activeVideo]);

	// Wiedergabe: Position merken und dort fortsetzen („Weiterschauen“).
	const playerRef = useRef(null);
	const lastSavedRef = useRef(0);
	// Zielposition fürs Fortsetzen; wird beim ersten timeupdate angewendet.
	const pendingResumeRef = useRef(0);
	// Zählt hoch, wenn sich gespeicherte Positionen geändert haben könnten —
	// MainPanel liest „Weiterschauen“ dann neu ein.
	const [progressVersion, setProgressVersion] = useState(0);

	const handleSelectVideo = useCallback((video, options = {}) => {
		lastSavedRef.current = 0;
		pendingResumeRef.current = options.fromStart ? 0 : getProgress(video.FilePath);
		returnFocusRef.current = options.returnFocus || Spotlight.getCurrent();
		setActiveVideo(video);
	}, []);

	const savePosition = useCallback(() => {
		const player = playerRef.current;
		if (!player || !activeVideo) return;
		const {currentTime, duration} = player.getMediaState();
		saveProgress(activeVideo.FilePath, currentTime, duration);
	}, [activeVideo]);
	useEffect(() => {
		saveRef.current = savePosition;
	}, [savePosition]);

	// Alle fünf Sekunden sichern — ein abgestürzter Player soll nicht alles
	// verlieren.
	//
	// Das Fortsetzen passiert ebenfalls hier, beim ersten timeupdate: In
	// onLoadedMetadata hält Limestone die Quelle noch für „nicht verfügbar“
	// und verwirft seek() still — gemessen startete das Video bei 0.
	const handleTimeUpdate = useCallback(() => {
		if (pendingResumeRef.current > 0 && playerRef.current) {
			const resumeAt = pendingResumeRef.current;
			pendingResumeRef.current = 0;
			playerRef.current.seek(resumeAt);
			return;
		}
		const now = Date.now();
		if (now - lastSavedRef.current < 5000) return;
		lastSavedRef.current = now;
		savePosition();
	}, [savePosition]);

	// Player schließen: Position sichern, „Weiterschauen“ auffrischen, Fokus
	// zurück auf die Kachel, von der aus gestartet wurde.
	const closePlayer = useCallback(() => {
		saveRef.current();
		setProgressVersion(v => v + 1);
		setActiveVideo(null);
		const target = returnFocusRef.current;
		returnFocusRef.current = null;
		setTimeout(() => {
			if (target && document.body.contains(target)) Spotlight.focus(target);
		}, 0);
	}, []);

	const handleAuthFailed = useCallback(() => {
		setActiveVideo(null);
		setPanelIndex(LOGIN);
	}, []);

	const handleLoginSuccess = useCallback(() => {
		setPanelIndex(MAIN);
		setReloadKey(k => k + 1);
	}, []);

	// Back-Taste (webOS: 461, ESC: 27) bei offenem Player: zurück zur
	// Übersicht, nicht „App beenden“. Auf window und im Capture — das läuft vor
	// den Document-Listenern der Hauptansicht (Detailansicht, Collection),
	// sonst schlösse dieselbe Taste dahinter noch eine Collection.
	useEffect(() => {
		const handleBackKey = (ev) => {
			if (ev.keyCode !== 461 && ev.keyCode !== 27) return;
			if (!activeVideoRef.current) return;
			ev.preventDefault();
			ev.stopImmediatePropagation();
			closePlayer();
		};
		window.addEventListener('keydown', handleBackKey, {capture: true});
		return () => window.removeEventListener('keydown', handleBackKey, {capture: true});
	}, [closePlayer]);

	// Zurück aus dem Hintergrund (Home-Taste, anderes Programm): Bibliothek
	// neu laden. Startet der Server zwischendurch neu, verfällt die Sitzung —
	// so landet man am Login statt vor Kacheln ohne Bilder.
	useEffect(() => {
		let hiddenAt = 0;
		const onVisibility = () => {
			if (document.hidden) {
				hiddenAt = Date.now();
			} else if (hiddenAt && Date.now() - hiddenAt > 60000 && !activeVideoRef.current) {
				setReloadKey(k => k + 1);
			}
		};
		const onRelaunch = () => {
			if (!activeVideoRef.current) setReloadKey(k => k + 1);
		};
		document.addEventListener('visibilitychange', onVisibility);
		document.addEventListener('webOSRelaunch', onRelaunch);
		return () => {
			document.removeEventListener('visibilitychange', onVisibility);
			document.removeEventListener('webOSRelaunch', onRelaunch);
		};
	}, []);

	const sessionToken = getItem('arcade_session_token', '');

	return (
		<div {...props} className={css.app}>
			<Panels index={panelIndex} noCloseButton>
				<MainPanel
					key={reloadKey}
					onSelectVideo={handleSelectVideo}
					onAuthFailed={handleAuthFailed}
					progressVersion={progressVersion}
				/>
				<LoginPanel onLoginSuccess={handleLoginSuccess} />
			</Panels>
			{activeVideo && panelIndex === MAIN ? (
				<PlayerLayer className={css.player} spotlightId="player-layer">
					<VideoPlayer
						ref={playerRef}
						title={displayName(activeVideo)}
						poster={posterUrl(activeVideo.FilePath)}
						onBack={closePlayer}
						onTimeUpdate={handleTimeUpdate}
						autoCloseTimeout={3000}
					>
						<Video>
							<source src={serverUrl(`/stream?path=${encodeURIComponent(activeVideo.FilePath)}&token=${encodeURIComponent(sessionToken || '')}`)} />
						</Video>
					</VideoPlayer>
				</PlayerLayer>
			) : null}
		</div>
	);
};

export default ThemeDecorator(App);
