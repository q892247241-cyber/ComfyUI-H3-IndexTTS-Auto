"""ComfyUI: H3 prompt -> IndexTTS 2.5 script automatic converter."""
from .h3_dialogue_parser import extract_h3_dialogue

class H3DialogueExtractToIndexTTS:
    CATEGORY = 'H3 / IndexTTS / 自动台词提取'
    FUNCTION = 'extract'
    RETURN_TYPES = ('STRING','STRING')
    RETURN_NAMES = ('IndexTTS批量脚本文本','提取检查报告JSON')

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'h3_prompt':('STRING',{'multiline':True,'default':''}),
            'default_role':(['角色A','角色B','角色C'],{'default':'角色A'}),
            'strict':('BOOLEAN',{'default':True}),
            'allow_multi_role':('BOOLEAN',{'default':False}),
        },'optional': {
            'role_aliases_json':('STRING',{'multiline':True,'default':''}),
        }}

    def extract(self,h3_prompt,default_role,strict=True,allow_multi_role=False,role_aliases_json=''):
        return extract_h3_dialogue(h3_prompt,default_role,role_aliases_json,strict,allow_multi_role)

NODE_CLASS_MAPPINGS={'H3DialogueExtractToIndexTTS':H3DialogueExtractToIndexTTS}
NODE_DISPLAY_NAME_MAPPINGS={'H3DialogueExtractToIndexTTS':'H3 → IndexTTS 自动提取台词/情绪'}

class H3DurationFromTTS:
    """读取实际合成语音时长，输出H3片段最低请求秒数（现有帧对齐节点再处理）。"""
    CATEGORY = 'H3 / IndexTTS / 自动台词提取'
    FUNCTION = 'duration'
    RETURN_TYPES = ('FLOAT','STRING')
    RETURN_NAMES = ('H3视频请求秒数','语音时长报告JSON')

    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{
            'audio':('AUDIO',),
            'min_seconds':('FLOAT',{'default':4.0,'min':0.5,'max':28.0,'step':0.5}),
            'tail_padding_seconds':('FLOAT',{'default':0.40,'min':0.0,'max':3.0,'step':0.05}),
            'max_audio_seconds':('FLOAT',{'default':15.0,'min':1.0,'max':60.0,'step':1.0}),
        }}

    def duration(self,audio,min_seconds=4.0,tail_padding_seconds=0.4,max_audio_seconds=15.0):
        import json
        wave=audio['waveform']; sr=int(audio['sample_rate'])
        if sr<=0: raise ValueError('TTS audio sample_rate 无效')
        n=int(wave.shape[-1]); spoken=n/sr
        if n<=0: raise ValueError('IndexTTS 输出空音频')
        if spoken>float(max_audio_seconds):
            raise ValueError('TTS 声音 %.2fs 超出单段 H3 音频参考上限 %.2fs：请拆句/拆镜头'%(spoken,max_audio_seconds))
        value=max(float(min_seconds), spoken+float(tail_padding_seconds))
        if value>28.0:
            raise ValueError('计算出来的H3时长超过28秒，请拆分镜头')
        return (float(value),json.dumps({'tts_seconds':round(spoken,3),'requested_seconds':round(value,3),
            'min_seconds':min_seconds,'tail_padding_seconds':tail_padding_seconds},ensure_ascii=False))

NODE_CLASS_MAPPINGS['H3DurationFromTTS']=H3DurationFromTTS
NODE_DISPLAY_NAME_MAPPINGS['H3DurationFromTTS']='H3 时长跟随 IndexTTS 原声音频'
