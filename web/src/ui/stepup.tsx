// Confirmação de identidade para operação sensível (v0.25.0).
//
// O servidor exige que a sessão confirme a identidade (senha e, com segundo fator, o código do
// aplicativo) antes de operações como acionar o interruptor de emergência, fechar período contábil
// ou aprovar instrução de pagamento. Vale 15 minutos. Este componente é a única tela que pede essa
// confirmação: o cliente da API o chama quando recebe `step_up_required` e repete a chamada.
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, onStepUpRequired } from "../api";
import { stepUp } from "../access";
import { useSession } from "../session";
import { Button, Field, Input, Modal } from "./kit";

export function StepUpProvider({ children }: { children: ReactNode }) {
  const { me } = useSession();
  const [aberto, setAberto] = useState(false);
  const [senha, setSenha] = useState("");
  const [codigo, setCodigo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  // Várias chamadas podem pedir confirmação ao mesmo tempo: todas esperam a MESMA resposta.
  const pendente = useRef<{ promessa: Promise<boolean>; resolver: (ok: boolean) => void } | null>(null);

  useEffect(() => {
    if (!me) { onStepUpRequired(null); return; }
    onStepUpRequired(() => {
      if (!pendente.current) {
        let resolver: (ok: boolean) => void = () => {};
        const promessa = new Promise<boolean>((r) => { resolver = r; });
        pendente.current = { promessa, resolver };
        setSenha(""); setCodigo(""); setErro(null); setAberto(true);
      }
      return pendente.current.promessa;
    });
    return () => onStepUpRequired(null);
  }, [me]);

  function terminar(ok: boolean) {
    setAberto(false);
    pendente.current?.resolver(ok);
    pendente.current = null;
  }

  async function confirmar() {
    setEnviando(true);
    setErro(null);
    try {
      await stepUp(senha, me?.user.mfa_enabled ? codigo : undefined);
      terminar(true);
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : "Não foi possível confirmar a identidade.");
    } finally {
      setEnviando(false);
    }
  }

  const precisaCodigo = !!me?.user.mfa_enabled;
  return (
    <>
      {children}
      <Modal open={aberto} title="Confirme sua identidade" onClose={() => terminar(false)}
             footer={<>
               <Button variant="ghost" onClick={() => terminar(false)}>Cancelar</Button>
               <Button busy={enviando} disabled={!senha || (precisaCodigo && codigo.length < 6)} onClick={confirmar}>Confirmar</Button>
             </>}>
        <form className="form" onSubmit={(e) => { e.preventDefault(); confirmar(); }}>
          <p className="muted small">
            Esta operação é sensível. Confirme que é você; a confirmação vale por 15 minutos nesta sessão.
          </p>
          <Field label="Senha"><Input type="password" autoComplete="current-password" value={senha} onChange={setSenha} /></Field>
          {precisaCodigo && (
            <Field label="Código do aplicativo autenticador">
              <Input inputMode="numeric" autoComplete="one-time-code" value={codigo} onChange={setCodigo} />
            </Field>
          )}
          {erro && <p className="error" role="alert">{erro}</p>}
          <button type="submit" hidden />
        </form>
      </Modal>
    </>
  );
}
