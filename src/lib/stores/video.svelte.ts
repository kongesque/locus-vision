function createVideoStore() {
    let videoUrl = $state<string | null>(null);
    let videoType = $state<'file' | 'url' | null>(null);

    return {
        get videoUrl() {
            return videoUrl;
        },
        get videoType() {
            return videoType;
        },
        setVideoUrl: (url: string | null) => {
            videoUrl = url;
        },
        setVideoType: (type: 'file' | 'url' | null) => {
            videoType = type;
        }
    };
}

export const videoStore = createVideoStore();
