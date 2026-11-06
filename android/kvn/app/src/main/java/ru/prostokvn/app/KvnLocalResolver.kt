package ru.prostokvn.app

import android.net.DnsResolver
import android.net.Network
import android.os.Build
import android.os.CancellationSignal
import android.system.ErrnoException
import android.util.Log
import io.nekohasekai.libbox.ExchangeContext
import io.nekohasekai.libbox.LocalDNSTransport
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.asExecutor
import kotlinx.coroutines.runBlocking
import java.net.InetAddress
import java.net.UnknownHostException
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.coroutines.resume
import kotlin.coroutines.suspendCoroutine

/**
 * Android native DNS bridge for sing-box libbox.
 *
 * Follows the LocalResolver approach in official sing-box-for-android (GPLv3).
 * Uses Android DnsResolver on the physical Network, not arbitrary hardcoded
 * public DNS servers or the app's VPN (tun) Network. Never logs DNS names.
 */
class KvnLocalResolver(private val networkProvider: () -> Network?) : LocalDNSTransport {
    private val firstSuccess = AtomicBoolean(false)
    private val firstFailure = AtomicBoolean(false)
    private val rcodeServfail = 2
    private val rcodeNxdomain = 3

    override fun raw(): Boolean = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q

    private fun networkOrError(ctx: ExchangeContext): Network? {
        val network = networkProvider()
        if (network == null) {
            if (firstFailure.compareAndSet(false, true)) {
                Log.w("KVN", "Android DNS: no physical upstream network")
            }
            ctx.errorCode(rcodeServfail)
        }
        return network
    }

    private fun reportFailure(ctx: ExchangeContext, exception: DnsResolver.DnsException) {
        val cause = exception.cause
        if (firstFailure.compareAndSet(false, true)) {
            Log.w("KVN", "Android physical DNS failed (${cause?.javaClass?.simpleName ?: exception.javaClass.simpleName})")
        }
        if (cause is ErrnoException) ctx.errnoCode(cause.errno)
        else ctx.errorCode(rcodeServfail)
    }

    override fun exchange(ctx: ExchangeContext, message: ByteArray) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            ctx.errorCode(rcodeServfail)
            return
        }
        val network = networkOrError(ctx) ?: return
        runBlocking {
            suspendCoroutine<Unit> { continuation ->
                val signal = CancellationSignal()
                val done = AtomicBoolean(false)
                fun finish() {
                    if (done.compareAndSet(false, true)) continuation.resume(Unit)
                }
                ctx.onCancel {
                    signal.cancel()
                    finish()
                }
                try {
                    DnsResolver.getInstance().rawQuery(
                        network, message, DnsResolver.FLAG_NO_RETRY,
                        Dispatchers.IO.asExecutor(), signal,
                        object : DnsResolver.Callback<ByteArray> {
                            override fun onAnswer(answer: ByteArray, rcode: Int) {
                                if (done.get()) return
                                if (rcode == 0) {
                                    if (firstSuccess.compareAndSet(false, true))
                                        Log.i("KVN", "Android physical DNS: first raw answer received")
                                    ctx.rawSuccess(answer)
                                } else ctx.errorCode(rcode)
                                finish()
                            }
                            override fun onError(error: DnsResolver.DnsException) {
                                if (done.get()) return
                                reportFailure(ctx, error)
                                finish()
                            }
                        }
                    )
                } catch (e: Exception) {
                    if (!done.get()) {
                        if (firstFailure.compareAndSet(false, true))
                            Log.w("KVN", "Android physical DNS: raw query rejected (${e.javaClass.simpleName})")
                        ctx.errorCode(rcodeServfail)
                    }
                    finish()
                }
            }
        }
    }

    override fun lookup(ctx: ExchangeContext, network: String, domain: String) {
        val upstream = networkOrError(ctx) ?: return
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            try {
                val answer = upstream.getAllByName(domain)
                ctx.success(answer.mapNotNull { it.hostAddress }.joinToString("\n"))
            } catch (_: UnknownHostException) {
                ctx.errorCode(rcodeNxdomain)
            }
            return
        }
        runBlocking {
            suspendCoroutine<Unit> { continuation ->
                val signal = CancellationSignal()
                val done = AtomicBoolean(false)
                fun finish() {
                    if (done.compareAndSet(false, true)) continuation.resume(Unit)
                }
                ctx.onCancel {
                    signal.cancel()
                    finish()
                }
                val callback = object : DnsResolver.Callback<Collection<InetAddress>> {
                    override fun onAnswer(answer: Collection<InetAddress>, rcode: Int) {
                        if (done.get()) return
                        if (rcode == 0) {
                            if (firstSuccess.compareAndSet(false, true))
                                Log.i("KVN", "Android physical DNS: first lookup answer received")
                            ctx.success(answer.mapNotNull { it.hostAddress }.joinToString("\n"))
                        } else ctx.errorCode(rcode)
                        finish()
                    }
                    override fun onError(error: DnsResolver.DnsException) {
                        if (done.get()) return
                        reportFailure(ctx, error)
                        finish()
                    }
                }
                try {
                    val type = when {
                        network.endsWith("4") -> DnsResolver.TYPE_A
                        network.endsWith("6") -> DnsResolver.TYPE_AAAA
                        else -> null
                    }
                    if (type == null) DnsResolver.getInstance().query(upstream, domain,
                        DnsResolver.FLAG_NO_RETRY, Dispatchers.IO.asExecutor(), signal, callback)
                    else DnsResolver.getInstance().query(upstream, domain, type,
                        DnsResolver.FLAG_NO_RETRY, Dispatchers.IO.asExecutor(), signal, callback)
                } catch (e: Exception) {
                    if (!done.get()) {
                        if (firstFailure.compareAndSet(false, true))
                            Log.w("KVN", "Android physical DNS: lookup rejected (${e.javaClass.simpleName})")
                        ctx.errorCode(rcodeServfail)
                    }
                    finish()
                }
            }
        }
    }
}
