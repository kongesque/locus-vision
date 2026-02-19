import { getContext, setContext } from 'svelte';

const VIDEO_KEY = Symbol('VIDEO');

export interface VideoState {
    videoUrl: string | null;
    videoType: 'file' | 'stream' | 'rtsp' | null;
    videoStream: MediaStream | null;
    videoConfig: any | null;
}

export class VideoStore {
    videoUrl = $state<string | null>(null);
    videoType = $state<'file' | 'stream' | 'rtsp' | null>(null);
    videoStream = $state<MediaStream | null>(null);
    videoConfig = $state<any | null>(null);

    constructor(initialState?: Partial<VideoState>) {
        if (initialState) {
            this.videoUrl = initialState.videoUrl ?? null;
            this.videoType = initialState.videoType ?? null;
            this.videoStream = initialState.videoStream ?? null;
            this.videoConfig = initialState.videoConfig ?? null;
        }
    }

    setVideo(type: 'file' | 'stream' | 'rtsp', source: string | MediaStream, config?: any) {
        this.videoType = type;
        this.videoConfig = config || null;

        if (type === 'file' && typeof source === 'string') {
            this.videoUrl = source;
            this.videoStream = null;
        } else if (type === 'stream' && source instanceof MediaStream) {
            this.videoStream = source;
            this.videoUrl = null;
        } else if (type === 'rtsp' && typeof source === 'string') {
            this.videoUrl = null;
            this.videoStream = null;
            this.videoConfig = { url: source, ...config };
        }
    }

    reset() {
        this.videoUrl = null;
        this.videoType = null;
        this.videoStream = null;
        this.videoConfig = null;
    }
}

export function setVideoContext(initialState?: Partial<VideoState>) {
    return setContext(VIDEO_KEY, new VideoStore(initialState));
}

export function useVideo() {
    return getContext<VideoStore>(VIDEO_KEY);
}
