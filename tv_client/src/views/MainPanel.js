import React, {useState, useEffect, useCallback} from 'react';
import PropTypes from 'prop-types';
import {Panel, Header} from '@enact/limestone/Panels';
import TabLayout, {Tab} from '@enact/limestone/TabLayout';
import {VirtualGridList} from '@enact/limestone/VirtualList';
import ImageItem from '@enact/limestone/ImageItem';
import ri from '@enact/ui/resolution';

const MainPanel = ({onSelectVideo, onAuthFailed, ...props}) => {
	const [allVideos, setAllVideos] = useState([]);
	const [loading, setLoading] = useState(true);

	// Daten laden
	useEffect(() => {
		fetch('http://192.168.2.183:8000/api/videos', {credentials: 'include'})
			.then(res => {
				if (res.status === 401) {
					if (onAuthFailed) onAuthFailed();
					throw new Error('Unauthorized');
				}
				if (!res.ok) throw new Error('Network error');
				return res.json();
			})
			.then(data => {
				// Dateinamen aufbereiten
				data.forEach(v => {
					const path = v.FilePath;
					const lastIdx = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
					v._fileName = path.substring(lastIdx + 1);
				});
				setAllVideos(data);
				setLoading(false);
			})
			.catch(err => {
				console.error('Fetch error:', err);
				setLoading(false);
			});
	}, [onAuthFailed]);

	// Filtergruppen erstellen
	const videos = allVideos.filter(v => (v.media_type || 'video') === 'video' && !v.hidden);
	const favorites = allVideos.filter(v => v.favorite && !v.hidden);
	const recent = [...allVideos].filter(v => !v.hidden).reverse().slice(0, 24);
	const images = allVideos.filter(v => v.media_type === 'image' && !v.hidden);
	const vault = allVideos.filter(v => v.hidden);

	// Item Renderer Factory
	const makeRenderer = useCallback((list) => ({index, ...itemProps}) => {
		const v = list[index];
		if (!v) return null;
		
		const isImage = v.media_type === 'image';
		const labelText = [
			v.Size_MB ? `${v.Size_MB.toFixed(1)} MB` : '',
			v.resolution || ''
		].filter(Boolean).join(' | ');

		return (
			<ImageItem
				{...itemProps}
				src={`http://192.168.2.183:8000/thumbnails/${v.thumb}`}
				label={labelText}
				onClick={() => onSelectVideo(v)}
				wideImage={!isImage}
			>
				{v._fileName}
			</ImageItem>
		);
	}, [onSelectVideo]);

	return (
		<Panel {...props}>
			<Header 
				title="Arcade Scanner TV" 
				subtitle={loading ? "Lade Mediathek..." : `${videos.length} Videos geladen`}
			/>
			
			{!loading && (
				<TabLayout>
					<Tab title="Alle Videos" icon="movies">
						<VirtualGridList
							dataSize={videos.length}
							itemRenderer={makeRenderer(videos)}
							itemSize={{
								minWidth: ri.scale(320),
								minHeight: ri.scale(240)
							}}
							direction="vertical"
						/>
					</Tab>
					<Tab title="Favoriten" icon="star">
						<VirtualGridList
							dataSize={favorites.length}
							itemRenderer={makeRenderer(favorites)}
							itemSize={{
								minWidth: ri.scale(320),
								minHeight: ri.scale(240)
							}}
							direction="vertical"
						/>
					</Tab>
					<Tab title="Letzte Importe" icon="history">
						<VirtualGridList
							dataSize={recent.length}
							itemRenderer={makeRenderer(recent)}
							itemSize={{
								minWidth: ri.scale(320),
								minHeight: ri.scale(240)
							}}
							direction="vertical"
						/>
					</Tab>
					<Tab title="Bilder" icon="picture">
						<VirtualGridList
							dataSize={images.length}
							itemRenderer={makeRenderer(images)}
							itemSize={{
								minWidth: ri.scale(240),
								minHeight: ri.scale(240)
							}}
							direction="vertical"
						/>
					</Tab>
					<Tab title="Archiv" icon="files">
						<VirtualGridList
							dataSize={vault.length}
							itemRenderer={makeRenderer(vault)}
							itemSize={{
								minWidth: ri.scale(320),
								minHeight: ri.scale(240)
							}}
							direction="vertical"
						/>
					</Tab>
				</TabLayout>
			)}
		</Panel>
	);
};

MainPanel.propTypes = {
	onSelectVideo: PropTypes.func.isRequired,
	onAuthFailed: PropTypes.func
};

export default MainPanel;
