import pytz
import random
from datetime import datetime, timedelta
from collections import defaultdict

from nonebot import get_bot
from nonebot import CommandSession, MessageSegment, NoneBot
from nonebot import permission as perm
from hoshino.util import silence, concat_pic, pic2b64
from hoshino.service import Service, Privilege as Priv
from .gacha import Gacha
from ..chara import Chara


__plugin_name__ = 'gacha'
sv = Service('gacha', manage_priv=Priv.SUPERUSER)
_last_gacha_day = -1
_user_jewel_used = defaultdict(int)    # {user: jewel_used}
_max_jewel_per_day = 135000
_group_pool=defaultdict(str)
gacha_10_aliases = ('十连', '十连！', '十连抽', '来个十连', '来发十连', '来次十连', '抽个十连', '抽发十连', '抽次十连', '十连扭蛋', '扭蛋十连',
                    '10连', '10连！', '10连抽', '来个10连', '来发10连', '来次10连', '抽个10连', '抽发10连', '抽次10连', '10连扭蛋', '扭蛋10连',
                    '十連', '十連！', '十連抽', '來個十連', '來發十連', '來次十連', '抽個十連', '抽發十連', '抽次十連', '十連轉蛋', '轉蛋十連',
                    '10連', '10連！', '10連抽', '來個10連', '來發10連', '來次10連', '抽個10連', '抽發10連', '抽次10連', '10連轉蛋', '轉蛋10連')
gacha_1_aliases = ('单抽', '单抽！', '来发单抽', '来个单抽', '来次单抽', '扭蛋单抽', '单抽扭蛋',
                   '單抽', '單抽！', '來發單抽', '來個單抽', '來次單抽', '轉蛋單抽', '單抽轉蛋')
gacha_300_aliases = ('抽一井', '来一井', '来发井', '抽发井',
                     '天井扭蛋', '扭蛋天井', '天井轉蛋', '轉蛋天井')

GACHA_DISABLE_NOTICE = '本群转蛋功能已禁用\n如欲开启，请与维护组联系'
GACHA_EXCEED_NOTICE = '您今天仅剩{}颗钻石了，不能再{}了！'
Pool=('TWGACHA_POOL','BGACHA_POOL','JPGACHA_POOL')

@sv.on_command('卡池资讯', deny_tip=GACHA_DISABLE_NOTICE, aliases=('查看卡池', '看看卡池', '康康卡池', '卡池資訊','看看up','看看UP'), only_to_me=False)
async def gacha_info(session: CommandSession):
    gid=session.ctx['group_id']
    await check_pool(session)
    gacha = Gacha(_group_pool[gid])
    up_chara = gacha.up
    if get_bot().config.IS_CQPRO:
        up_chara = map(lambda x: str(
            Chara.fromname(x).icon.cqcode) + x, up_chara)
    up_chara = '\n'.join(up_chara)
    await session.send(f"本期卡池主打的角色：\n{up_chara}\nUP角色合计={(gacha.up_prob/10):.1f}% 3星出率={(gacha.s3_prob)/10:.1f}%")


async def check_gacha_num(session,str,surplus,num):
    global _last_gacha_day, _user_jewel_used
    user_id = session.ctx['user_id']
    now = datetime.now(pytz.timezone('Asia/Shanghai'))
    day = (now - timedelta(hours=5)).day
    if day != _last_gacha_day:
        _last_gacha_day = day
        _user_jewel_used.clear()
    if surplus<num:
        session.finish(GACHA_EXCEED_NOTICE.format(f'{surplus}',f'{str}'),at_sender=True)


@sv.on_rex(r'^选择([国台日]服)卡池',normalize=False, event='group')
async def choose_pool(bot:NoneBot,ctx,match):
    global _group_pool
    if not await sv.check_permission(ctx, required_priv=Priv.ADMIN):
        await bot.send(ctx,'只有管理员才可以选择卡池',at_sender=False)
        return
    group_id=ctx['group_id']
    is_guo=match.group(1)=='国服'
    is_tai=match.group(1)=='台服'
    is_ri=match.group(1)=='日服'
    if not is_guo and not is_tai and not is_ri:
        await bot.send(ctx,'\n请问您要选择哪个服务器的卡池？\n选择国服卡池\n选择台服卡池',at_sender=True)
    else:
        if is_guo:
            _group_pool[group_id]=Pool[1]
            await bot.send(ctx,'选择国服卡池成功',at_sender=True)
        if is_tai:
            _group_pool[group_id]=Pool[0]
            await bot.send(ctx,'选择台服卡池成功',at_sender=True)
        if is_ri:
            _group_pool[group_id]=Pool[2]
            await bot.send(ctx,'选择日服卡池成功',at_sender=True)

async def check_pool(session):
    global _group_pool
    group_id=session.ctx['group_id']
    if _group_pool[group_id]=='':
        session.finish('请联系管理员选择卡池后再抽卡', at_sender=True)


@sv.on_command('gacha_1', deny_tip=GACHA_DISABLE_NOTICE, aliases=gacha_1_aliases, only_to_me=False)
async def gacha_1(session: CommandSession):
    uid = session.ctx['user_id']
    group_id=session.ctx['group_id']
    await check_pool(session)
    surplus = _max_jewel_per_day-_user_jewel_used[uid]
    await check_gacha_num(session,'单抽',surplus,150)
    _user_jewel_used[uid] += 150
    surplus = _max_jewel_per_day-_user_jewel_used[uid]
    gacha = Gacha(_group_pool[group_id])
    chara, hiishi = gacha.gacha_one(
        gacha.up_prob, gacha.s3_prob, gacha.s2_prob)
    silence_time = hiishi * 60

    res = f'{chara.name} {"★"*chara.star}'
    if get_bot().config.IS_CQPRO:
        res = f'{chara.icon.cqcode} {res}'

    await silence(session.ctx, silence_time)
    await session.send(f'素敵な仲間が増えますよ！\n{res}\n您今天还剩下{surplus}颗钻！', at_sender=True)


@sv.on_command('gacha_10', deny_tip=GACHA_DISABLE_NOTICE, aliases=gacha_10_aliases, only_to_me=False)
async def gacha_10(session: CommandSession):

    SUPER_LUCKY_LINE = 170
    uid = session.ctx['user_id']
    group_id=session.ctx['group_id']
    await check_pool(session)
    surplus = _max_jewel_per_day-_user_jewel_used[uid]
    await check_gacha_num(session,'十连',surplus,1500)
    _user_jewel_used[uid] += 1500
    surplus = _max_jewel_per_day-_user_jewel_used[uid]
    gacha = Gacha(_group_pool[group_id])
    result, hiishi = gacha.gacha_ten()
    silence_time = hiishi * 6 if hiishi < SUPER_LUCKY_LINE else hiishi * 60

    if get_bot().config.IS_CQPRO:
        res1 = Chara.gen_team_pic(result[:5], star_slot_verbose=False)
        res2 = Chara.gen_team_pic(result[5:], star_slot_verbose=False)
        res = concat_pic([res1, res2])
        res = pic2b64(res)
        res = MessageSegment.image(res)
        result = [f'{c.name}{"★"*c.star}' for c in result]
        res1 = ' '.join(result[0:5])
        res2 = ' '.join(result[5:])
        res = res + f'{res1}\n{res2}'
    else:
        result = [f'{c.name}{"★"*c.star}' for c in result]
        res1 = ' '.join(result[0:5])
        res2 = ' '.join(result[5:])
        res = f'{res1}\n{res2}'

    await silence(session.ctx, silence_time)
    if hiishi >= SUPER_LUCKY_LINE:
        await session.send('恭喜海豹！おめでとうございます！')
    await session.send(f'素敵な仲間が増えますよ！\n{res}\n您今天还剩下{surplus}颗钻！', at_sender=True)


@sv.on_command('gacha_300', deny_tip=GACHA_DISABLE_NOTICE, aliases=gacha_300_aliases, only_to_me=False)
async def gacha_300(session: CommandSession):

    uid = session.ctx['user_id']
    group_id=session.ctx['group_id']
    await check_pool(session)
    surplus = _max_jewel_per_day-_user_jewel_used[uid]
    await check_gacha_num(session,'一井',surplus,45000)
    _user_jewel_used[uid] += 45000
    surplus = _max_jewel_per_day-_user_jewel_used[uid]
    gacha = Gacha(_group_pool[group_id])
    result = gacha.gacha_tenjou()
    up = len(result['up'])
    s3 = len(result['s3'])
    s2 = len(result['s2'])
    s1 = len(result['s1'])

    res = [*(result['up']), *(result['s3'])]
    random.shuffle(res)
    lenth = len(res)
    if lenth <= 0:
        res = "竟...竟然没有3★？！"
    else:
        step = 4
        pics = []
        for i in range(0, lenth, step):
            j = min(lenth, i + step)
            pics.append(Chara.gen_team_pic(res[i:j], star_slot_verbose=False))
        res = concat_pic(pics)
        res = pic2b64(res)
        res = MessageSegment.image(res)

    msg = [
        "素敵な仲間が増えますよ！",
        f"您今天还剩下{surplus}颗钻！",
        str(res),
        f"共计{up+s3}个3★，{s2}个2★，{s1}个1★",
        f"获得{100*up}个记忆碎片与{50*(up+s3) + 10*s2 + s1}个女神秘石！\n第{result['first_up_pos']}抽首次获得up角色" if up else f"获得{50*(up+s3) + 10*s2 + s1}个女神秘石！"
    ]

    if up == 0 and s3 == 0:
        msg.append("太惨了，咱们还是退款删游吧...")
    elif up == 0 and s3 > 7:
        msg.append("up呢？我的up呢？")
    elif up == 0 and s3 <= 3:
        msg.append("这位酋长，梦幻包考虑一下？")
    elif up == 0:
        msg.append("据说天井的概率只有12.16%")
    elif up <= 2 and result['first_up_pos'] < 50:
        msg.append("已经可以了，您已经很欧了")
    elif up <= 2:
        msg.append("期望之内，亚洲水平")
    elif up == 3:
        msg.append("抽井母五一气呵成！多出30等专武～")
    elif up >= 4:
        msg.append("6★的碎片都有了，您是托吧？")

    silence_time = (100*up + 50*(up+s3) + 10*s2 + s1) * 1
    await silence(session.ctx, silence_time)
    await session.send('\n'.join(msg), at_sender=True)


@sv.on_rex(r'^氪金$', normalize=False)
async def kakin(bot:NoneBot, ctx, match):
    if ctx['user_id'] not in bot.config.SUPERUSERS:
        return
    count = 0
    for m in ctx['message']:
        if m.type == 'at' and m.data['qq'] != 'all':
            _user_jewel_used[int(m.data['qq'])] = 0
            count += 1
    if count:
        await bot.send(ctx, f"已为{count}位用户充值完毕！谢谢惠顾～", at_sender=True)
