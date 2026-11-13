/* Original optional reporter against official Java 1.21.4 classes.
 * Resolves count handling through the real ItemStack codec without starting
 * a game/server. Run with the same classpath as PrimaryStateReport.java. */
import java.lang.reflect.*;
public class PrimaryItemReport {
 public static void main(String[] args) throws Exception {
  var out=System.out;
  Class.forName("ab").getMethod("a").invoke(null);
  Class.forName("akx").getMethod("a").invoke(null);
  Class<?> ops=Class.forName("com.mojang.serialization.DynamicOps");
  Object jsonOps=Class.forName("com.mojang.serialization.JsonOps").getField("INSTANCE").get(null);
  Object registry=Class.forName("mb").getField("aC").get(null);
  Object provider=Class.forName("kf").getMethod("a",Class.forName("ke")).invoke(null,registry);
  Object registryOps=Class.forName("akt").getMethod("a",ops,Class.forName("jt$a")).invoke(null,jsonOps,provider);
  Object codec=Class.forName("cwq").getField("a").get(null);
  Method parse=Class.forName("com.mojang.serialization.Decoder").getMethod("parse",ops,Object.class);
  Method json=Class.forName("com.google.gson.JsonParser").getMethod("parseString",String.class);
  for(int count:new int[]{0,1,99,100,200})out.println("COUNT "+count+" "+parse.invoke(codec,registryOps,json.invoke(null,"{\"id\":\"minecraft:diamond\",\"count\":"+count+"}")));
  Field levels=Class.forName("ddg").getDeclaredField("d");levels.setAccessible(true);
  for(int level:new int[]{0,1,255,256,32767})out.println("ENCHANTMENT_LEVEL "+level+" "+parse.invoke(levels.get(null),jsonOps,json.invoke(null,Integer.toString(level))));
 }
}
