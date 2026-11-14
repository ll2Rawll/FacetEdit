/* Original optional black-box reporter for official Java 1.21.4 methods.
 * A synthetic read-only BlockGetter supplies state IDs from a text file.
 * The server is not started and no executable game code is redistributed. */
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

public class PrimaryContextReport {
 public static void main(String[] args) throws Exception {
  var out=System.out;
  Class.forName("ab").getMethod("a").invoke(null);
  Class.forName("akx").getMethod("a").invoke(null);
  Class<?> block=Class.forName("djn"),state=Class.forName("dwy"),getter=Class.forName("dfo"),position=Class.forName("ji");
  Object zero=position.getField("c").get(null);
  Method byId=block.getMethod("a",int.class),idOf=block.getMethod("j",state),getBlock=state.getMethod("b");
  Method connection=Class.forName("dpu").getDeclaredMethod("a",getter,state,position);connection.setAccessible(true);
  Method fluid=state.getMethod("y");Object air=byId.invoke(null,0);
  for(String line:Files.readAllLines(Path.of(args[0]))) {
   String[] fields=line.split(" ");Map<Object,Object> world=new HashMap<>();Object source=byId.invoke(null,Integer.parseInt(fields[1]));world.put(zero,source);
   for(int i=2;i<fields.length;i+=4)world.put(position.getConstructor(int.class,int.class,int.class).newInstance(Integer.parseInt(fields[i]),Integer.parseInt(fields[i+1]),Integer.parseInt(fields[i+2])),byId.invoke(null,Integer.parseInt(fields[i+3])));
   Object view=Proxy.newProxyInstance(getter.getClassLoader(),new Class<?>[]{getter},(proxy,method,values)->{
    if(method.getName().equals("a_")&&values.length==1)return world.getOrDefault(values[0],air);
    if(method.getName().equals("b_")&&values.length==1)return fluid.invoke(world.getOrDefault(values[0],air));
    if(method.getName().equals("c_"))return null;
    if(method.isDefault())return InvocationHandler.invokeDefault(proxy,method,values);
    throw new IllegalStateException("Unimplemented getter method: "+method);
   });
   Object result=connection.invoke(getBlock.invoke(source),view,source,zero);
   out.println("WIRE "+fields[0]+" "+idOf.invoke(null,result));
  }
  Class<?> ops=Class.forName("com.mojang.serialization.DynamicOps");
  Object jsonOps=Class.forName("com.mojang.serialization.JsonOps").getField("INSTANCE").get(null);
  Object registry=Class.forName("mb").getField("aC").get(null);
  Object provider=Class.forName("kf").getMethod("a",Class.forName("ke")).invoke(null,registry);
  Object registryOps=Class.forName("akt").getMethod("a",ops,Class.forName("jt$a")).invoke(null,jsonOps,provider);
  Object codec=Class.forName("cwq").getField("a").get(null);
  Method parse=Class.forName("com.mojang.serialization.Decoder").getMethod("parse",ops,Object.class);
  Method json=Class.forName("com.google.gson.JsonParser").getMethod("parseString",String.class);
  int i=0;
  for(String line:Files.readAllLines(Path.of(args[1])))out.println("ITEM "+(i++)+" "+parse.invoke(codec,registryOps,json.invoke(null,line)));
  if(args.length>2) {
   Class<?> entity=Class.forName("dua"),compound=Class.forName("tq"),lookup=Class.forName("jt$a");
   Method create=Class.forName("dmg").getMethod("a",position,state);
   Method read=entity.getMethod("c",compound,lookup),save=entity.getMethod("d",lookup);
   Method snbt=Class.forName("uo").getMethod("a",String.class);
   for(String line:Files.readAllLines(Path.of(args[2]))) {
    String[] fields=line.split("\t",3);
    try {
     Object value=byId.invoke(null,Integer.parseInt(fields[1])),be=create.invoke(getBlock.invoke(value),zero,value);
     read.invoke(be,snbt.invoke(null,fields[2]),provider);
     out.println("PAYLOAD "+fields[0]+" "+save.invoke(be,provider));
    } catch(InvocationTargetException error) {out.println("PAYLOAD_ERROR "+fields[0]+" "+error.getCause());}
   }
  }
 }
}
