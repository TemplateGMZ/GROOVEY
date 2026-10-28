package aoko.render;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;

// Invoked by Aoko's native bridge. Does not depend on Fabric classes at compile time.
// Reflectively registers with Fabric WorldRenderEvents.LAST when present in the game.
public final class WorldMatrixTap implements InvocationHandler {
    private static volatile Object listener;
    private static Method matrixGetter;
    private static Method viewGetter;
    private static Method projectionGetter;
    private static volatile boolean active;

    public static native void onMatrices(float[] positionMatrix, float[] projectionMatrix);

    public static synchronized boolean install(ClassLoader loader) {
        if (active) return true;
        try {
            Class<?> events = Class.forName(
                "net.fabricmc.fabric.api.client.rendering.v1.WorldRenderEvents", false, loader);
            Class<?> callbackType = Class.forName(
                "net.fabricmc.fabric.api.client.rendering.v1.WorldRenderEvents$Last", false, loader);
            Class<?> contextType = Class.forName(
                "net.fabricmc.fabric.api.client.rendering.v1.WorldRenderContext", false, loader);
            Class<?> eventType = Class.forName(
                "net.fabricmc.fabric.api.event.Event", false, loader);
            Class<?> matrixType = Class.forName("org.joml.Matrix4f", false, loader);
            viewGetter = contextType.getMethod("positionMatrix");
            projectionGetter = contextType.getMethod("projectionMatrix");
            matrixGetter = matrixType.getMethod("get", float[].class);
            Object event = events.getField("LAST").get(null);
            Object candidate = Proxy.newProxyInstance(loader,
                new Class<?>[]{callbackType}, new WorldMatrixTap());
            eventType.getMethod("register", Object.class).invoke(event, candidate);
            listener = candidate;
            active = true;
            return true;
        } catch (Throwable e) {
            return false;
        }
    }

    @Override
    public Object invoke(Object proxy, Method method, Object[] args) {
        if ("onLast".equals(method.getName()) && args != null && args.length == 1) {
            try {
                Object ctx = args[0];
                Object vm = viewGetter.invoke(ctx);
                Object pm = projectionGetter.invoke(ctx);
                if (vm != null && pm != null) {
                    float[] view = new float[16];
                    float[] proj = new float[16];
                    matrixGetter.invoke(vm, (Object)view);
                    matrixGetter.invoke(pm, (Object)proj);
                    onMatrices(view, proj);
                }
            } catch (Throwable ignored) {
                // The overlay retains its existing projection fallback.
            }
        }
        if ("hashCode".equals(method.getName())) return System.identityHashCode(proxy);
        if ("equals".equals(method.getName())) return args != null && args.length > 0 && proxy == args[0];
        if ("toString".equals(method.getName())) return "Aoko WorldMatrixTap";
        return null;
    }
}
