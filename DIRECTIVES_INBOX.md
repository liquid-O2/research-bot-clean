# DIRECTIVES_INBOX — hook-flagged candidate directives pending classification (promote to DIRECTIVES.md or clear at next boundary; hooks alarm while non-empty)
- [2026-08-11T10:55:49Z] Your finding was a bit weird for me. So I'm not sure why today's open would ever be a good level for us because we always move away from it.

The extremes shouldn't be anywhere near today's open. So could you plot things on the chart and look at things yourself? Like look at how it actually looks like, the entries and etc., the levels, because this does not seem right for me
- [2026-08-11T11:23:46Z] So since you said a ton of the entries are the same thing, but in the same leg, do you reckon we need to understand the path that we are taking? Like the path, or like the entire path that we have taken so far, and every feature and every piece of information that we have, and how it's developing over time?

Like, do we need a sequence model or something
- [2026-08-11T12:07:36Z] 27 hours of compute??? for something that we dont even know will work?
- [2026-08-11T12:09:49Z] such long hours are not acceptable when we dont even have every feature under the sun, its still a helf out feature set
- [2026-08-11T13:40:26Z] Also, since things are taking so long to compute and et cetera, and we have so many features, will it not be unfeasible for the live training phase? Like, are we doing a bit too much?

I'll be using Theta data live, so I'll have like six streams of data live. I cannot have more than that. So I'm not sure how exactly it works, but yeah, if we can.

Like the stack name that is supposed to be 34 hours still hasn't even started yet. It's still optimizing it, and it's been running for hours and hours on end now, just trying to optimize. Like the run hasn't even begun yet.

Is it worth it to trim some of it down to the highest quality ones? Like I'm not sure how this works, but yeah, I just don't want to waste 36 hours of compute on an expensive run pod machine to get a null result
- [2026-08-11T14:35:10Z] Okay, so you don't really understand exactly what we talked about. Remember what I exactly talked about?

We have third-order Greeks which are not using the thing you mentioned, the fast dealer reflex positioning layer, et cetera. Those make no sense unless we factor in IV and how it adapts, as well as how the dealer hedging is actually working. That is the stock tip as well as the third-order gigs, how they're reacting for that.

Like you are still doing the basic stuff
- [2026-08-11T15:20:14Z] Yeah, but after you do the blind case with tax and et cetera, you need to act on it as well because I suspect it will take no more than a few hours at max. So I don't want you to be like waiting on something like or waiting on me. I want you to be autonomous
- [2026-08-11T15:36:00Z] Yeah, but even the things you mentioned needed my sign-off. Like, I don't think that needs my sign-off. Like, I don't want us to, like, waste time, if that makes sense. Like, I don't know how to describe it
- [2026-08-12T03:52:16Z] Also remember the thing you did, like where you looked at ten trades to find out which one will work or not? Did the entire day's chart render already? So wouldn't you have been able to infer what trade it was?

Like was it done properly? Like did you only get the OHLC or chart up until before your decision point? And if you can get the traits done properly or easily, would it be worth it to? Like if nothing else works, maybe you can go through hundreds of traits, find out exactly what works, what combination of things work, and then jot it down as proper notes.

And maybe there are some hidden patterns and et cetera that you notice that might not be explained via normal features, but you can create your own feature explaining that hidden pattern.

Basically, the thing that comes from discretion. so we always have this whole thing as a backup plan.
- [2026-08-12T03:55:13Z] Yeah, but the formalized systematic backup program needs to have all the context and all the data that we have. Basically all of the I. V. state and et cetera. Like it should not skimp out on the type of features and the sequence of features and everything that we are doing.

Like we'd still need proper features, like very descriptive ones like Bidasque I. V. and features derived from Bidasque I. V., like the skew and. Like other novel ideas of it, like we don't want to just stick with the basic definitions of stuff that everyone has used.

Also tapes across streams. Also the interest rate. I think we get delayed once so we can get like. Uh, we have interest rate data, uh, from Fred, I guess. But we need to have every single data in their best format and everything.

I know you are very good at it, but I'm because it's extremely expensive for me to have you make trading decisions all the time like in live environment. So if we can get this done via a simple model based on your discretion and your way of thinking, that would be really helpful.

But first, we'll take a look at our current path, if it makes sense or if it does better or not.
- [2026-08-12T05:40:55Z] Yeah, I'm just wondering if our distillation process would have actually been a better idea, and would that process actually help us for other assets as well? For example, crypto or copper or N.K.D.

Like for crypto data, we can download the data from Binance, Bybit, and et cetera, like for free, and also Hyperliquid. As well as we can get Deribit data for options as well, if you believe that's a better way of handling things.

So this whole strategy we are building by the way is basically for proforma futures proforma. So we'll execute on R2Y futures and using like one mini at max two minis, spanning across five accounts, copy traded.

I was also thinking what if we do the same for N.K.D. and copper futures as well, or do a complete three sixty and look into crypto perpetual futures or options with my own money instead of platforms.

With that, I would be able to put in like around two thousand dollars. Nothing more than that, but crypto gives us higher leverage and we don't have to abide by any rules.

We can do the scalping route as well with like hundreds of trades a day. I'm fine with that, so even if every trade is like very few percentage return, because we will be taking so many trades a day, we can compound quickly.

And probably out earn what our five proforma accounts would make from just one to two R2Y minis, copy traded together, I guess, but that's just like my theory. I'm not too sure about it
- [2026-08-12T06:59:46Z] Yeah, for question number one, I'm specifically meant like instead of training these large models, I, what if we just built the features properly and had you do the distillation and then put your decision making, et cetera, via simple features and rules and et cetera into a cheap model, like an XGBoost or TappPFN version three with the checkpoints and et cetera, or maybe CatBoost?

Like wouldn't that have been much faster than the twenty-hour block?

And for the crypto stuff, the low-frequency extreme capture, the stuff is like I just want, for crypto, if we have crypto, then this two per two k should be our starting point, and I want to outearn our profit.

If that makes sense, maybe we could do it with options. Maybe we could do it with perpetual futures with leverage. I'm not sure which one is the best option, but yeah, we need to basically compound our capital extremely quickly, which is kinda unheard of and sounds absurd when you compare it to quants who make a few percentage points every year.

And we'd be aiming for a hundred X return in less than five months or so.

So yeah, that is something. Excitement, you've heard, but maybe it's because of our low capacity. Like we can't trade millions and get that same return because of how much the price would move.

So maybe it's doable for our port, but not for maybe quants. So it might be more achievable.

Like take a worst-case scenario of the returns we can get, like take a normal leverage like one to two twenty or something. And plot some of our trades and see how much we could potentially earn in crypto, then find out how we could compound it properly.

Like this is a toy problem. Just think about it in your head and then give me the answer.

Because if we can outearn five pro firms earning together with one crypto port in a few months, then I will keep working. I will, uh, we would spend the time developing the crypto thingy as well after this is done.

So we have a backup thingy already running, earning us mo
- [2026-08-12T07:06:52Z] No, like I think your math is a bit wrong. Like instead of three to four trades a day, like if we take all of the trades we can take per day, like you have seen, actually never mind.

So we'll take the highest confidence ones that give us the best returns, or like the proper calibration point where we get the returns properly. Or like the best point between the return versus amount of trades taken, and we can deploy in BTC, ETH as well as Solana.

So we have like multiple streams working together, and I think we can earn more than three percent per day. Right, like if we take a higher leverage, so fifteen x will have a minimum of twenty x leverage
- [2026-08-12T07:09:39Z] Yeah, let's put a pin on the crypto stuff. We don't want to waste more time on that.

Let's focus on our current model, and I don't understand the numbers you're posting. By the way, it's two point zero, three, one, two point zero, four, seven.

And like, I don't understand how good it is compared to the others. Like, it's a smaller number, but it feels like a very low number, if that makes sense
- [2026-08-12T07:46:11Z] And the overlay that I talked to you about, like this ivx tape, is not the only overlay we'll have. We'll have multiple things working together as well.

The other thing is, if you want to, after this first mining round, you can do another mining round with more features and stuff built from the P.D.F.s that I shared. I'll also send you some more P.D.F.s.

Run the command I'll send to basically download the P.D.F. so that I want to share, like look through those to understand more discretionary patterns and stuff alongside the other P.D.F.s that you have, and the action state from the video thingy that we talked about.

Maybe those could help make the decision much clearer.

And again, we need to ensure we get things done properly by the way. Like we need all the features that we can get, not just the basic ones, because basic ones barely give you any information.

Like order flow imbalance or V. Pin never gives you a proper actionable insight into something.

And we might need to have some overlap for Opus for checking your cases as well. Maybe it can find blind spots in your patents as well and find new patents and et cetera.

You will be the final decision maker, of course.

And like we need some way to make this work properly. We need to be able to get your discretion and stuff built into the actual models.
- [2026-08-12T07:49:47Z] Yeah, take into consideration the participation intent and et cetera, as well as different features derived from Ivy.

Like, we can create state-of-the-art versions or features or formulas that derive information from different streams—not the ones that have already been done.

Or maybe the things we have that have already been done can be used, but not the basic ones.

I don't know how to describe it, but we need the proper features and everything that we have discussed ever.

Like, I don't want us to stay stuck on the basic features and patterns that everyone does.  I don't know, like I feel like we can create so much more useful features and useful information out of it out of the raw data that we have. I still feel like our features currently are very basic and crude.
- [2026-08-12T07:55:06Z] Like, would it be better for you to look at the raw data for your trades and et cetera, instead of the hand-built features? So you can understand exactly what type of feature we can add.

Also, the urgency spectroscopy—I'm not sure if it's worth it or not, because, actually, never mind, it is. But again, the microstructure features, I'm not sure if that is helpful for our longer-term one, but again, I might be wrong about that as well.

So I'm just wondering if you should just get the proper raw data with proper time stamps, so you can understand what type of features we actually need and what you actually observed.

Like, you can jot everything that you observed down and what actually gave us the proper result. So even if you can't get something right, maybe you can actually go back and look at what the pattern was.

Maybe we can have a training period where you look at the surviving ones and the ones that don't work, and then learn the patterns from there. Maybe exactly like how a human would.

Like, we need to find a way to get this done, like in the most efficient and the most well-managed way, so we can just do it. We can just get it done at once, I guess.

I'm not sure. Just give me your ideas as well, your opinions on how you would like to do things
- [2026-08-12T08:01:15Z] Yeah, and we might also need to understand how the like, you know, this is. Uh, I'll try to explain it the best I can.

So basically, what will happen is, um, what actually happens is like, uh, let's say we start the market at nine thirty. The tape will already be like very twitchy and stuff. So if we are taking a trade decision near the market open, the pattern that will discover and et cetera will be no simply different than what we'll notice at, let's say eleven thirty or twelve when the tape will settle down.

So that is one thing—like the patterns can change intraday, and like the speed of the tape and et cetera changes as well.

The other thing is, um, the way the price was reacting, the way the features were evolving and the raw data was evolving or changing, or etcetera, coming to the extreme—like the way it changed. So maybe it was normal, then it suddenly started getting stronger and etcetera, or it had like this many orders previously, but now coming to the extreme, it's getting lower, or maybe more orders are coming in and it's not getting the, it's getting absorbed or something like etcetera, etcetera, like the ivy is changing.

Maybe the ivy predicted something—there's so much stuff we can do. I just don't want to like, uh, I don't want to miss out on anything.

And then the spread, the quarter vision size changes, the ivy, the expiry, the delta change, the like. I don't want us, uh, we don't want the zoom or the resolution to be smaller. Like you don't want us to just check the last five minutes of data or something like things might generally like be updating as we move.

So we need a lossless way of getting you to read it without having to read through millions and millions of events.

The other thing is, sometimes not all events have any meaning. We can filter it out for a specific amount of like, like a specific minimum rate or something. Although I'm not sure if that would reduce the value of the information we get because we won't see every sing
- [2026-08-12T08:35:21Z] Again, the direction should not be like unlearnable. Like, think about how you would understand it.

So let's say the price is moving down and we know this is a reversal model. We form a low, confirm that low has exhausted or like the whole discretion framework has completed. Then we'll obviously take a lock. There should not be any confusion about which direction to trade, right?

And I can. I'm not sure if we should waste time on fold two like using different stuff. You were able to get gauge the direction right on the trades you took. It's not something that is unknowable. It's already known from the beginning before you even place a trade, so it makes no sense.

And what was your results by the way for the seven for the eight trades you took like the? Profits you took per trade and et cetera. Like we need to find a way to transfer that over. Yeah, I'm still not sure about wasting our resources on fold two, whereas we should focus on the distillation process.
- [2026-08-12T08:43:11Z] What is running now, by the way, because we should be doing the trade thingy distillation right now.

And yeah, I'm just not like, what information did you use to capture that? Was it just a stock quote rates or something like that?

Because if we can capture entries like these, then I think we can add copper and N. K. D. futures as well. I have the level one data for those, so maybe we can capture more value out of it, like more great dollars thingy.

But I don't have the iv and et cetera for it. I know we have Axia with which we can get Chinese data easily for copper, but, yeah, I'm still not sure  like I'm not tied to a specific asset. I just need a future asset that I can get my goal with easily.
- [2026-08-12T10:21:59Z] And yeah, participant participation should not change with that. We need to adapt to the new patterns emerging that give us the proper thing, not just reduce our grades.

And again, I still feel like we are not using all of the data we can get because sixty-four percent decisive hit is not good enough. Did you try the training phase as well? Like seeing what works, what doesn't, and again, what works, what doesn't, and et cetera needs to.

Also, like adapt to things and etcetera, like we need to make things much more rich and etcetera like not.

And again, I also told you that we don't need the exact extreme. I think predicting the exact extreme is harder than confirming that the extreme has been formed. And then taking an entry like one to two one-minute bars after it, if that makes sense. Not more than that.

So if that is easier for you, then we should try to use that. We have significantly higher win rate and capturing the highest caption, highest captures, and two hundred thirty-seven dollars is extremely low. That is nowhere near what we want. I literally told you a thousand dollars or more.
- [2026-08-12T10:28:00Z] Yeah, but implied volatility and etcetera. Like, I need you to get through the raw data to understand how we can get things, and I don't want you to just learn things.

So because we have just five years of data, I don't want you to just discard the data you have already looked at. Maybe we can shuffle them and etcetera.

I'm not sure how we can do this, but we don't want to spend the entire five years on your training and etcetera. That way, we will never overfit and etcetera.

But I don't want you to learn the same threads you have learned either. But I don't want you to run out of the data that we have for the threads and et cetera.
- [2026-08-12T10:33:34Z] I don't know, man. It feels like we are going nowhere.

Like I need us to get there. Like I need you to find the best things. Like if you can get the best rates out from the data you can see, then that's amazing for us.

Like you saw that you could actually encode those for a normal model to learn, or any other improvements that we can make.

Like if you can find what works, you can easily express it so that normal models can learn it. So do that. Like round three should probably help us
- [2026-08-12T14:51:25Z] Okay, so continue, but again, we like went through thirty-nine percent of our weekly limit in less than an hour, as well as consumed our entire five-hour session limit at once.

So we need to find a token-efficient way of handling this without sacrificing on quality or the results that we'll get. We just got back our session limit, which will try to keep things efficient.
- [2026-08-12T15:06:10Z] So the reason I'm asking you to build the features based on what you see is the best fit is because you have the raw data and you use that raw data to take the decision, right?

So you can look back at all of the decisions you took, of the features or data that supported you taking an entry and features that prevented you from taking an entry and et cetera, and the data that supported it and like went against it and etc.

So that way we can build a sniper set of features, so we don't have to waste so much time on building every single feature out there and hoping it works.

Because you have the raw data, you can properly build the features that actually work for us.  and now we need to make sure we get things right, by the way. You have proven that you can take really good trades, but we need to transfer it over to a model with your decision-making skills.
- [2026-08-12T15:36:01Z] The roster offering $3,000 a day. That is the create you to quit. So it isn't even Oracle. It's actual create decisions.

So yeah, the features that did not work for the model, but it worked for you. You need to think about how you interpreted those features and how you can codify it and the other stuff that you might not even think about.

Basically, the hidden patterns are the discretion part of it. You need to codify it as well.

And $3,000 a day is doable. It's not Oracle. It's just the trades you took. So it's not hindsight, like perfect trades. It's just the trades that you took.

So we can get the best. We can get to that easily, right?

So we can improve the selection further. You need to codify your stuff better.

And also ask Opus 5 on Max effort to do the same thing you did. That is, look through the thingies and take grades and not done exactly what type of interaction, what data and etc. they used to get the grades done.

And now we need to improve everything further  you can get the features that actually make the decision and that actually help us. We can definitely use it for our stuff.

So first, I need you to ask Opus 5 to do so. Then you do it, but with less amount of trade so that we don't burn through our tokens and our usage limits. And then we will use, then we will try to build our features properly.

It gets the exact context and the exact thing that you see, and then we will look into exits after we have finalized our entries. Because currently it's nowhere near perfect.

I think you can also get over 3,028 a day if you do it properly with the new features and deeper features and etc.

And also look into the other gaps in the data that you have versus the raw data so we can see that video as well, so you can take better decisions and then you can build out features that help us.

This is essentially like a roundabout way of doing an abolition test because you can figure out what actually works without us having to add and remove stuff.  thi
- [2026-08-12T16:14:11Z] Yeah, but I need. So this is something that I'm actually curious about. Like, I'm not sure exactly what data you used. Like, did you have the proper granular data for like every single data field we have? Like all the Greeks, all the and how they evolve, all the quote tapes from the options, the stock, the IWM and the IOTW, all the Ivy stuff from both of the options. Maybe some other stuff from the stocks and options.

I want to ensure that you actually had access to all of the data. And in the training phase, I wanted you to take a look at all of the things that worked and did not work. Look at all the raw data for all of those grades, like, and find out the patterns, the hidden patterns and the things that worked and didn't.

And for those training periods, I want you to basically think of those grades like Try to take those traits and see if it fails or not. And when it fails, like take a look at what has happened, like why it failed, what was your thinking and what proved it wrong. Same with what works as well. Like even if you took the right trait, take a look at the data that was there, like and see like how you could have pinpointed it better and et cetera.

So that is the like work of the training phase. Like you need to do it for like different eras, different regimes as well for the training. And then look at the, then take like blind trades in the out of sample areas as well.

But again, this should be like walk forward based so you can learn things over time. Because again, as I've told you, the market evolves. The patterns that emerged some time ago might not work again. Like we might see other different patterns appear over time. And different regimes ask for different patents as well.

So I wanted us to have that granularity, but without wasting too many tokens, but not giving up on the quality as well, if that makes sense. So we need to ensure we do that, and we need to do that for like the granularest level of events stream and et cetera
- [2026-08-12T17:26:11Z] Yeah, but what I want you to do is you will have OpenCode CLI. I want you to use that to ask Grok 4.6 on high to do the same thing you and Opus did, but in better detail.

Ask it to go through everything that we did and tell it what to find, what type of data to use. And I think we can do better than this. Like, we can find better features and engrain things better so that we have more stuff.

Like, I'm not sure if you used the proper IV and all of the data that you needed, by the way. Like, you literally told me you don't have all of the data that you need to understand things properly.

So unless we have all of the data that we need and do this whole thing properly, not just on 20 days, but like a larger duration as well, I'm not comfortable moving to the exits.

Ask Grok to do a full pass and ask it to do it properly to find out exactly the discretion, the hidden patterns and interactions that we don't have.

Like, don't just ask it to find the one  just don't like, don't mention that specific thing, but let discover things itself.
- [2026-08-12T17:42:17Z] Just 2022 and 2023 won't tell us anything. From 2024 and onwards, the market changed completely.

So if we don't take 2024 and 2025 into account, we will not learn anything, and we will not be able to finalize our entries
- [2026-08-12T17:44:40Z] It's fine. We will leave the last four months of 2025 as well as 2026 alone for the blind testing.

We will keep 2024 and 2025 in testing as well, but we'll do walk-forward testing. So that will ensure that we don't like to, that will ensure that we can use 2024 and 2025 by the way.

2026 will remain a complete blind set that will not touch, but we will do walk-forward testing through 2025  across all events, all days, we will not leave days behind, because again, there might be some news events or other events that change our entire market structure and et cetera. So leaving them out will be a disservice to us.
- [2026-08-12T17:50:10Z] Yeah, what I want you to do is ensure we have all the data. You just mentioned the RUTW data is being extracted right now, but I remember us not having a ton of data. You mentioned it yourself, right? Like we did not have a ton of information with you, so we need to fill that gap as well.

Also, you mentioned that Opus is better at it than you are, so can you test that out? And also you have access to Codex as well. So ask GPT 5.6 on X height to do the same thing we did, by the way, just like with Croc.

So with these three additional models, we will discover blind spots and we will be able to create the best features possible so we get the exact best entries as well. And we might do the same thing on exits to understand how we would build our exit model to get the best results possible as well
- [2026-08-12T18:27:50Z] The other thing to understand is that we have a ton of research already with us, but we are barely using any of that research to build our information streams and et cetera.

But the thing is, before we spend time building new features over and over again, I want us to understand what the actual oracles are and what we are capturing. Like first, I need to know what you are capturing, you, Opus, and et cetera. Like the amount of I think we are capturing and comparing it to the Oracle, like how close we are to the Oracle.

Because if we are like 99 or like 95% or 90% of the Oracle, then I'm not sure if we need to invest in more features or not.

The other thing was for the IV, like you remember we had like a model that could predict the forward volatility. Maybe you could use that as well for your inputs and seeing the forward volatility forecast changing.

We were using hard ivory garment class as well as the buildask IV altogether into a single model that would predict the next volatility stuff. So maybe we could use that as an input for our entries as well, but I was also thinking it could also be used as the context area as well.

So if at the beginning of the day or pre-market, we like forecast the implied move of the day. Maybe it would help us time when we should look for our entries.

As the time progresses, we keep plotting forward volatility, like implied moves and stuff, and see what information that gives us.

And also, we can use different standard deviations or other improvements to the implied move to get the best level or something to trade off of.

Also, for exits, it might also help us. Know when we should exit as well later on, but that's for later
- [2026-08-12T20:03:50Z] We should have waited for all of the stuff to be added before we tried to let DeepSeek or GPT-like run through it.

And since Grok did no improvement, did not find anything useful for us, we'll just leave it out.

We'll see if DeepSeek is genuinely amazing.

We might use it for more decisions later on, but this is the last time we will be using DeepSeek, by the way.

Or actually, I will give you one last use of DeepSeek as well as GPT 5.6.

That is after we have everything that we need there and we need to properly do the testing and extraction and like the hidden pattern or the discretion extraction and everything else like properly.

So we understand exactly how they think, how we should use them, like what type of information we need and etc.

And you mentioned: Is the third order Greeks IV error and the options did?

You did not add the updated like IV data and etc.

Like it does not really make much sense.

Like I literally told you to have all of the features done.

You reported just a third order Greeks and stuff being added
- [2026-08-12T20:11:10Z] Also, the other thing is, I do understand that we don't need the 90% Oracle capture on days that have like over $5,000 per day, but on eras where we have just $2,000 to capture, like we need more, we need to capture more of the Oracle, right? Like what is holding us back and how can we reliably reach our goal and exceed it?

I'm fine with $1,500 by the way, at the very minimum. But that should also reflect in the drawdown. The drawdown needs to be extremely minimal as well.

Also, work through the exit system as well. After we had finalized with entries and like you have NKD as well as copper like data as well now, as well as silver. Although I'd mostly like to focus on Copper and NKD or NKD and Silver.

If we can get a similar system built there as well, then we could have like a portfolio system which would help us immensely. But that's a later thing. That will only happen after we have the entries and exits figured out and the blind thing used.

When we have a strategy for this, we will expand it to Copper, NKD and Silver. So if we have at least two assets, that will be a portfolio structure.

And don't quants prefer a portfolio rather than a single asset? That way we can cover our bases. Like if something is weak in one era, the other thing will cover it. And again, we can optimize our trades for like specific entries and stuff.

I'm not like I can't describe it, but yeah. Is there a way we can have the same rich data for Copper and KDE and Silver as we did for this?

We will have like proper CME like futures data level one with the events, by the way, not just normal event one, but normal level one, but like with events. So we have every event by event level one MVP one data.

So it's genuinely like substantial. And it's from data bent as well, so it will be extremely clean, unlike the data we have here.

So I have more expectation out of those, but I'm not sure the amount of money we can make that is. Like I am aware that IWM makes more money per day on the sa
- [2026-08-12T20:54:46Z] yea we consumed 20 more dollars, this is it, i dont wanna use any more tokens after this deepseek finishes
- [2026-08-13T02:48:52Z] Fifteen hundred was only for the weak errors. Two thousand is the thingy.

So again, if it's two thousand, we need to ensure we capture that hundred percent of it. So keep building on the exit regimes.

You should have been working on it. You have been staying silent for over six hours, last hours of sleep
- [2026-08-13T04:39:44Z] So we are able to get proper exits. Like what? What is going on? It should be doable.

Are you taking smarter ways to pick the exits or something? And no, I don't want to reach two thousand with just one with two minis. I want it to be. All of our value should be done with one mini.

And why did you mention two thousand if you knew our deployment is one position occupancy? It makes no sense 
